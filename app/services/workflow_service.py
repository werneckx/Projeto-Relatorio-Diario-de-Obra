"""
Serviço centralizado de resolução e execução de workflows de aprovação.

Responsabilidades:
- Resolver workflow aplicável (empresa/obra)
- Persistir a execução do workflow por RDO com snapshot das etapas
- Resolver aprovadores por usuário, papel e matriz de responsabilidade
- Registrar aprovações, rejeições e assinaturas em um único fluxo
- Bloquear edição pós-aprovação final
- Versionar RDO aprovado
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask_login import current_user

from app import db
from app.models.obra import ObraUsuario
from app.models.rdo import RDO, RDOAprovacao, RDOAssinatura, RDOVersao
from app.models.usuario import Papel, Usuario
from app.models.workflow import (
    WorkflowDefinicao,
    WorkflowEtapa,
    WorkflowExecucao,
    WorkflowExecucaoEtapa,
)
from app.services.auditoria_service import AuditoriaService
from app.services.config_service import ConfigService
from app.utils.datetime_utils import utcnow_naive
from app.utils.serializers import safe_model_to_dict


class WorkflowResolucaoError(Exception):
    """Erro ao resolver workflow."""


class WorkflowService:
    """Serviço centralizado de workflow."""

    DEFAULT_WORKFLOW_CODIGO = 'SIMPLES'

    # =========================================================================
    # RESOLUÇÃO DE WORKFLOW
    # =========================================================================

    @staticmethod
    def _resolver_workflow_obra(
        empresa_id: int,
        obra_id: Optional[int],
    ) -> Optional[WorkflowDefinicao]:
        if obra_id is None:
            return None
        return WorkflowDefinicao.query.filter_by(
            empresa_id=empresa_id,
            obra_id=obra_id,
            ativo=True,
        ).order_by(WorkflowDefinicao.id.asc()).first()

    @staticmethod
    def _resolver_workflow_empresa_por_codigo(
        empresa_id: int,
        codigo: Optional[str],
    ) -> Optional[WorkflowDefinicao]:
        codigo_normalizado = (codigo or '').strip()
        if not codigo_normalizado:
            return None
        return WorkflowDefinicao.query.filter(
            WorkflowDefinicao.empresa_id == empresa_id,
            WorkflowDefinicao.obra_id.is_(None),
            WorkflowDefinicao.ativo.is_(True),
            db.or_(
                db.func.upper(db.func.trim(WorkflowDefinicao.codigo)) == codigo_normalizado.upper(),
                db.func.upper(db.func.trim(WorkflowDefinicao.nome)) == codigo_normalizado.upper(),
            ),
        ).order_by(WorkflowDefinicao.id.asc()).first()

    @staticmethod
    def _resolver_workflow_empresa_padrao(empresa_id: int) -> Optional[WorkflowDefinicao]:
        try:
            codigo_padrao = ConfigService.obter_valor(
                empresa_id=empresa_id,
                obra_id=None,
                chave='workflow.default',
            )
        except Exception:
            codigo_padrao = None

        workflow = WorkflowService._resolver_workflow_empresa_por_codigo(
            empresa_id,
            codigo_padrao or WorkflowService.DEFAULT_WORKFLOW_CODIGO,
        )
        if workflow:
            return workflow

        return WorkflowDefinicao.query.filter_by(
            empresa_id=empresa_id,
            obra_id=None,
            ativo=True,
        ).order_by(WorkflowDefinicao.id.asc()).first()

    @staticmethod
    def resolver_workflow(
        empresa_id: int,
        obra_id: Optional[int],
    ) -> Optional[WorkflowDefinicao]:
        """Resolve o workflow aplicável pela cadeia obra -> empresa -> sistema."""
        workflow = WorkflowService._resolver_workflow_obra(empresa_id, obra_id)
        if workflow:
            return workflow

        return WorkflowService._resolver_workflow_empresa_padrao(empresa_id)

    @staticmethod
    def obter_etapas_ordenadas(workflow_id: int) -> List[WorkflowEtapa]:
        """Obtém etapas ativas do workflow em ordem estável."""
        return WorkflowEtapa.query.filter_by(
            workflow_id=workflow_id,
            ativo=True,
        ).order_by(
            WorkflowEtapa.nivel.asc(),
            WorkflowEtapa.ordem.asc().nullslast(),
            WorkflowEtapa.id.asc(),
        ).all()

    @staticmethod
    def obter_execucao_ativa(rdo_id: int) -> Optional[WorkflowExecucao]:
        return WorkflowExecucao.query.filter_by(
            rdo_id=rdo_id,
            ativo=True,
        ).order_by(WorkflowExecucao.id.desc()).first()

    # =========================================================================
    # RESOLUÇÃO DE RESPONSÁVEIS
    # =========================================================================

    @staticmethod
    def _resolver_papel_por_codigo(empresa_id: int, papel_codigo: Optional[str]) -> Optional[Papel]:
        if not papel_codigo:
            return None
        return Papel.query.filter(
            Papel.nome == papel_codigo,
            Papel.ativo.is_(True),
            db.or_(Papel.empresa_id == empresa_id, Papel.empresa_id.is_(None)),
        ).order_by(Papel.empresa_id.desc().nullsfirst(), Papel.id.asc()).first()

    def _resolver_aprovador(
        etapa: WorkflowEtapa,
        rdo: Optional[RDO] = None,
    ) -> Optional[int]:
        """
        Resolve o aprovador de uma etapa.

        Prioridade:
        1. Usuário específico
        2. Responsável da obra (quando aplicável)
        3. Matriz explícita workflow_responsaveis
        4. Papel alocado na obra
        5. Papel atribuído ao usuário na empresa
        """
        if etapa.usuario_aprovador_id:
            return etapa.usuario_aprovador_id

        papel = etapa.papel
        if papel is None and etapa.papel_codigo:
            papel = WorkflowService._resolver_papel_por_codigo(etapa.empresa_id, etapa.papel_codigo)

        if etapa.tipo_aprovador == 'RESPONSAVEL_OBRA' and rdo and rdo.obra and rdo.obra.usuario_responsavel_id:
            return rdo.obra.usuario_responsavel_id

        if etapa.tipo_aprovador == 'CLIENTE' and papel is None:
            papel = WorkflowService._resolver_papel_por_codigo(etapa.empresa_id, 'CLIENTE_OBRA')

        papel_id = papel.id if papel else etapa.papel_id
        if not papel_id:
            return None

        if rdo:
            usuario_obra = (
                db.session.query(ObraUsuario)
                .join(Usuario, Usuario.id == ObraUsuario.usuario_id)
                .filter(
                    ObraUsuario.empresa_id == etapa.empresa_id,
                    ObraUsuario.obra_id == rdo.obra_id,
                    ObraUsuario.papel_id == papel_id,
                    ObraUsuario.ativo.is_(True),
                    Usuario.ativo.is_(True),
                )
                .order_by(ObraUsuario.id.asc())
                .first()
            )
            if usuario_obra:
                return usuario_obra.usuario_id

        return None

    # =========================================================================
    # SNAPSHOT E EXECUÇÃO
    # =========================================================================

    @staticmethod
    def _ator_id() -> Optional[int]:
        return getattr(current_user, 'id', None)

    @staticmethod
    def _workflow_snapshot(workflow: WorkflowDefinicao, etapas: Iterable[WorkflowEtapa]) -> Dict[str, Any]:
        return {
            'workflow_id': workflow.id,
            'codigo': workflow.codigo,
            'nome': workflow.nome,
            'descricao': workflow.descricao,
            'tipo_fluxo': workflow.tipo_fluxo,
            'obra_id': workflow.obra_id,
            'empresa_id': workflow.empresa_id,
            'aprovacao_paralela': workflow.aprovacao_paralela,
            'rejeicao_cancela_fluxo': workflow.rejeicao_cancela_fluxo,
            'cliente_obrigatorio': workflow.cliente_obrigatorio,
            'assinatura_obrigatoria': workflow.assinatura_obrigatoria,
            'permite_reprovar': workflow.permite_reprovar,
            'permite_reabertura': workflow.permite_reabertura,
            'permite_cancelamento': workflow.permite_cancelamento,
            'sla_horas': workflow.sla_horas,
            'sla_global_horas': workflow.sla_global_horas,
            'etapas': [
                {
                    'id': etapa.id,
                    'nivel': etapa.nivel,
                    'ordem': etapa.ordem,
                    'codigo': etapa.codigo,
                    'nome': etapa.nome,
                    'tipo_aprovador': etapa.tipo_aprovador,
                    'papel_id': etapa.papel_id,
                    'papel_codigo': etapa.papel_codigo,
                    'usuario_aprovador_id': etapa.usuario_aprovador_id,
                    'grupo_paralelo': etapa.grupo_paralelo,
                    'obrigatorio': etapa.obrigatorio,
                    'obrigatoria': etapa.obrigatoria,
                    'assinatura_obrigatoria': etapa.assinatura_obrigatoria,
                    'sla_horas': etapa.sla_horas,
                }
                for etapa in etapas
            ],
        }

    @staticmethod
    def _etapa_snapshot(etapa: WorkflowEtapa, aprovador_id: Optional[int]) -> Dict[str, Any]:
        return {
            'etapa_id': etapa.id,
            'nivel': etapa.nivel,
            'ordem': etapa.ordem,
            'codigo': etapa.codigo,
            'nome': etapa.nome,
            'tipo_aprovador': etapa.tipo_aprovador,
            'papel_id': etapa.papel_id,
            'papel_codigo': etapa.papel_codigo,
            'usuario_aprovador_id': etapa.usuario_aprovador_id,
            'usuario_resolvido_id': aprovador_id,
            'grupo_paralelo': etapa.grupo_paralelo,
            'obrigatorio': etapa.obrigatorio,
            'obrigatoria': etapa.obrigatoria,
            'assinatura_obrigatoria': etapa.assinatura_obrigatoria,
            'sla_horas': etapa.sla_horas,
            'permite_reprovar': etapa.permite_reprovar,
            'comentario_reprovacao_obrigatorio': etapa.comentario_reprovacao_obrigatorio,
        }

    @staticmethod
    def _invalidar_execucao_ativa(rdo_id: int) -> None:
        execucao = WorkflowService.obter_execucao_ativa(rdo_id)
        if execucao:
            execucao.ativo = False
            execucao.finalizado_em = utcnow_naive()
            execucao.modificado_por = WorkflowService._ator_id()
            execucao.modificado_em = utcnow_naive()
            db.session.add(execucao)

        for aprovacao in RDOAprovacao.query.filter_by(rdo_id=rdo_id, ativo=True).all():
            aprovacao.ativo = False
            aprovacao.modificado_por = WorkflowService._ator_id()
            aprovacao.modificado_em = utcnow_naive()
            db.session.add(aprovacao)

    @staticmethod
    def iniciar_execucao(
        rdo_id: int,
        workflow_id: Optional[int] = None,
        sobrescrever: bool = False,
        origem: str = 'AUTO',
    ) -> WorkflowExecucao:
        rdo = db.session.get(RDO, rdo_id)
        if not rdo:
            raise WorkflowResolucaoError(f"RDO {rdo_id} não encontrado")

        workflow = db.session.get(WorkflowDefinicao, workflow_id) if workflow_id else WorkflowService.resolver_workflow(
            rdo.empresa_id,
            rdo.obra_id,
        )
        if not workflow:
            raise WorkflowResolucaoError(f"Nenhum workflow ativo encontrado para o RDO {rdo_id}")

        etapas = WorkflowService.obter_etapas_ordenadas(workflow.id)
        if not etapas:
            raise WorkflowResolucaoError(f"Workflow {workflow.id} não possui etapas ativas")

        execucao_ativa = WorkflowService.obter_execucao_ativa(rdo.id)
        if execucao_ativa and not sobrescrever:
            return execucao_ativa
        if execucao_ativa and sobrescrever:
            WorkflowService._invalidar_execucao_ativa(rdo.id)

        actor_id = WorkflowService._ator_id()
        snapshot = WorkflowService._workflow_snapshot(workflow, etapas)
        execucao = WorkflowExecucao(
            empresa_id=rdo.empresa_id,
            obra_id=rdo.obra_id,
            rdo_id=rdo.id,
            workflow_id=workflow.id,
            status='EM_ANDAMENTO',
            etapa_atual_nivel=1,
            workflow_snapshot=snapshot,
            origem=origem,
            criado_por=actor_id,
            modificado_por=actor_id,
        )
        db.session.add(execucao)
        db.session.flush()

        aprovacoes_criadas: List[RDOAprovacao] = []
        for etapa in etapas:
            aprovador_id = WorkflowService._resolver_aprovador(etapa, rdo)
            if not aprovador_id:
                raise WorkflowResolucaoError(f"Etapa {etapa.id} não possui aprovador definido")

            etapa_execucao = WorkflowExecucaoEtapa(
                empresa_id=rdo.empresa_id,
                execucao_id=execucao.id,
                etapa_definicao_id=etapa.id,
                nivel=etapa.nivel,
                ordem=etapa.ordem,
                nome=etapa.nome,
                tipo_aprovador=etapa.tipo_aprovador,
                papel_id=etapa.papel_id,
                usuario_resolvido_id=aprovador_id,
                grupo_paralelo=etapa.grupo_paralelo,
                obrigatorio=etapa.obrigatorio,
                assinatura_obrigatoria=etapa.assinatura_obrigatoria,
                sla_horas=etapa.sla_horas,
                etapa_snapshot=WorkflowService._etapa_snapshot(etapa, aprovador_id),
                criado_por=actor_id,
                modificado_por=actor_id,
            )
            db.session.add(etapa_execucao)

            aprovacao = RDOAprovacao(
                empresa_id=rdo.empresa_id,
                rdo_id=rdo.id,
                aprovador_id=aprovador_id,
                nivel=1 if workflow.aprovacao_paralela else etapa.nivel,
                status='PENDENTE',
                ativo=True,
                criado_por=actor_id,
            )
            db.session.add(aprovacao)
            aprovacoes_criadas.append(aprovacao)

        db.session.flush()
        return execucao

    @staticmethod
    def salvar_fluxo_manual(
        rdo_id: int,
        usuarios_ids: List[int],
        sobrescrever: bool = True,
    ) -> List[RDOAprovacao]:
        rdo = db.session.get(RDO, rdo_id)
        if not rdo:
            raise WorkflowResolucaoError(f"RDO {rdo_id} não encontrado")

        if sobrescrever:
            WorkflowService._invalidar_execucao_ativa(rdo_id)

        actor_id = WorkflowService._ator_id()
        execucao = WorkflowExecucao(
            empresa_id=rdo.empresa_id,
            obra_id=rdo.obra_id,
            rdo_id=rdo.id,
            workflow_id=WorkflowService.resolver_workflow(rdo.empresa_id, rdo.obra_id).id
            if WorkflowService.resolver_workflow(rdo.empresa_id, rdo.obra_id)
            else 0,
            status='EM_ANDAMENTO',
            etapa_atual_nivel=1 if usuarios_ids else None,
            workflow_snapshot={
                'tipo': 'MANUAL',
                'usuarios_ids': usuarios_ids,
            },
            origem='MANUAL',
            criado_por=actor_id,
            modificado_por=actor_id,
        )
        db.session.add(execucao)
        db.session.flush()

        aprovacoes: List[RDOAprovacao] = []
        for index, usuario_id in enumerate(usuarios_ids, start=1):
            etapa_execucao = WorkflowExecucaoEtapa(
                empresa_id=rdo.empresa_id,
                execucao_id=execucao.id,
                etapa_definicao_id=None,
                nivel=index,
                ordem=index,
                nome=f'Aprovador {index}',
                tipo_aprovador='USUARIO',
                usuario_resolvido_id=usuario_id,
                obrigatorio=True,
                assinatura_obrigatoria=False,
                etapa_snapshot={
                    'tipo_aprovador': 'USUARIO',
                    'usuario_resolvido_id': usuario_id,
                    'nivel': index,
                },
                criado_por=actor_id,
                modificado_por=actor_id,
            )
            db.session.add(etapa_execucao)

            aprovacao = RDOAprovacao(
                empresa_id=rdo.empresa_id,
                rdo_id=rdo.id,
                aprovador_id=usuario_id,
                nivel=index,
                status='PENDENTE',
                ativo=True,
                criado_por=actor_id,
            )
            db.session.add(aprovacao)
            aprovacoes.append(aprovacao)

        rdo.status = 'PENDENTE'
        rdo.modificado_por = actor_id
        rdo.modificado_em = utcnow_naive()
        db.session.add(rdo)
        db.session.flush()
        return aprovacoes

    @staticmethod
    def gerar_aprovacoes_por_etapas(
        rdo_id: int,
        workflow_id: int,
    ) -> List[RDOAprovacao]:
        execucao = WorkflowService.iniciar_execucao(
            rdo_id=rdo_id,
            workflow_id=workflow_id,
            sobrescrever=True,
            origem='AUTO',
        )
        return RDOAprovacao.query.filter_by(
            rdo_id=rdo_id,
            ativo=True,
        ).order_by(RDOAprovacao.nivel.asc(), RDOAprovacao.id.asc()).all()

    # =========================================================================
    # APROVAÇÃO / REJEIÇÃO / ASSINATURA
    # =========================================================================

    @staticmethod
    def _obter_etapa_execucao_por_aprovacao(aprovacao: RDOAprovacao) -> Optional[WorkflowExecucaoEtapa]:
        execucao = WorkflowService.obter_execucao_ativa(aprovacao.rdo_id)
        if not execucao:
            return None

        etapa = WorkflowExecucaoEtapa.query.filter_by(
            execucao_id=execucao.id,
            usuario_resolvido_id=aprovacao.aprovador_id,
            ativo=True,
        ).filter(
            WorkflowExecucaoEtapa.status == 'PENDENTE',
        ).order_by(
            WorkflowExecucaoEtapa.nivel.asc(),
            WorkflowExecucaoEtapa.ordem.asc().nullslast(),
            WorkflowExecucaoEtapa.id.asc(),
        ).first()
        return etapa

    @staticmethod
    def _registrar_assinatura_formal(
        aprovacao: RDOAprovacao,
        assinatura_path: Optional[str],
        ip: Optional[str],
        user_agent: Optional[str],
        hash_doc: Optional[str],
    ) -> None:
        if not assinatura_path:
            return

        usuario = aprovacao.aprovador
        colaborador_id = getattr(usuario, 'colaborador_id', None)
        if not colaborador_id:
            return

        tipo_assinatura = 'CLIENTE'
        try:
            papel_nomes = {(p.nome or '').strip().upper() for p in (usuario.papeis or [])}
            if 'CLIENTE_OBRA' not in papel_nomes:
                tipo_assinatura = 'INTERNO'
        except Exception:
            tipo_assinatura = 'INTERNO'

        assinatura = RDOAssinatura.query.filter_by(
            rdo_id=aprovacao.rdo_id,
            usuario_id=aprovacao.aprovador_id,
        ).order_by(RDOAssinatura.id.desc()).first()

        if not assinatura:
            assinatura = RDOAssinatura(
                empresa_id=aprovacao.empresa_id,
                rdo_id=aprovacao.rdo_id,
                usuario_id=aprovacao.aprovador_id,
                colaborador_id=colaborador_id,
                tipo_assinatura=tipo_assinatura,
                status='ASSINADO',
                hash_documento=hash_doc or aprovacao.hash or assinatura_path,
                ip=ip,
                user_agent=user_agent,
                assinado_em=utcnow_naive(),
            )
        else:
            assinatura.colaborador_id = colaborador_id
            assinatura.tipo_assinatura = tipo_assinatura
            assinatura.status = 'ASSINADO'
            assinatura.hash_documento = hash_doc or aprovacao.hash or assinatura.hash_documento
            assinatura.ip = ip
            assinatura.user_agent = user_agent
            assinatura.assinado_em = utcnow_naive()

        db.session.add(assinatura)

    @staticmethod
    def _validar_ordem_sequencial(aprovacao: RDOAprovacao) -> Tuple[bool, str]:
        execucao = WorkflowService.obter_execucao_ativa(aprovacao.rdo_id)
        if not execucao:
            return True, ""
        if execucao.workflow_snapshot.get('aprovacao_paralela'):
            return True, ""

        pendencias_anteriores = RDOAprovacao.query.filter(
            RDOAprovacao.rdo_id == aprovacao.rdo_id,
            RDOAprovacao.ativo.is_(True),
            RDOAprovacao.status != 'APROVADO',
            RDOAprovacao.nivel < aprovacao.nivel,
        ).count()
        if pendencias_anteriores > 0:
            return False, "Aguarde a aprovação do responsável anterior."
        return True, ""

    @staticmethod
    def _todas_etapas_aprovadas(rdo_id: int) -> bool:
        execucao = WorkflowService.obter_execucao_ativa(rdo_id)
        if execucao:
            pendentes_obrigatorias = WorkflowExecucaoEtapa.query.filter_by(
                execucao_id=execucao.id,
                ativo=True,
                obrigatorio=True,
                status='PENDENTE',
            ).count()
            return pendentes_obrigatorias == 0

        pendentes = RDOAprovacao.query.filter_by(
            rdo_id=rdo_id,
            status='PENDENTE',
            ativo=True,
        ).count()
        return pendentes == 0

    @staticmethod
    def _atualizar_status_execucao(rdo_id: int) -> None:
        execucao = WorkflowService.obter_execucao_ativa(rdo_id)
        if not execucao:
            return

        pendente = WorkflowExecucaoEtapa.query.filter_by(
            execucao_id=execucao.id,
            ativo=True,
            status='PENDENTE',
        ).order_by(
            WorkflowExecucaoEtapa.nivel.asc(),
            WorkflowExecucaoEtapa.ordem.asc().nullslast(),
            WorkflowExecucaoEtapa.id.asc(),
        ).first()

        execucao.etapa_atual_nivel = pendente.nivel if pendente else None

        status_values = {
            row.status
            for row in WorkflowExecucaoEtapa.query.filter_by(execucao_id=execucao.id, ativo=True).all()
        }
        if 'REJEITADO' in status_values:
            execucao.status = 'REJEITADO'
        elif 'CANCELADO' in status_values and 'PENDENTE' not in status_values:
            execucao.status = 'CANCELADO'
        elif 'PENDENTE' in status_values:
            execucao.status = 'EM_ANDAMENTO'
        else:
            execucao.status = 'APROVADO'
            execucao.finalizado_em = utcnow_naive()

        execucao.modificado_por = WorkflowService._ator_id()
        execucao.modificado_em = utcnow_naive()
        db.session.add(execucao)

    @staticmethod
    def processar_acao(
        aprovacao_id: int,
        acao: str,
        comentario: Optional[str] = None,
        motivo: Optional[str] = None,
        ip: Optional[str] = None,
        hash_doc: Optional[str] = None,
        assinatura_path: Optional[str] = None,
        user_agent: Optional[str] = None,
        reabrir: bool = False,
        commit: bool = True,
    ) -> Tuple[bool, str]:
        try:
            aprovacao = db.session.get(RDOAprovacao, aprovacao_id)
            if not aprovacao or not aprovacao.ativo:
                return False, "Aprovação não encontrada"
            if aprovacao.status != 'PENDENTE':
                return False, f"Aprovação já foi {aprovacao.status.lower()}"

            ok_ordem, mensagem_ordem = WorkflowService._validar_ordem_sequencial(aprovacao)
            if not ok_ordem and acao in {'APPROVE', 'SIGN', 'REJECT'}:
                return False, mensagem_ordem

            actor_id = WorkflowService._ator_id()
            rdo = db.session.get(RDO, aprovacao.rdo_id)
            if not rdo:
                return False, "RDO não encontrado"

            workflow = WorkflowService.resolver_workflow(rdo.empresa_id, rdo.obra_id)
            etapa_execucao = WorkflowService._obter_etapa_execucao_por_aprovacao(aprovacao)

            if acao in {'APPROVE', 'SIGN'}:
                aprovacao.status = 'APROVADO'
                aprovacao.data_aprovacao = utcnow_naive()
                aprovacao.comentario = comentario
                aprovacao.endereco_ip = ip
                aprovacao.hash = hash_doc
                if assinatura_path:
                    aprovacao.imagem_assinatura = assinatura_path
                aprovacao.modificado_por = actor_id
                aprovacao.modificado_em = utcnow_naive()
                db.session.add(aprovacao)

                if etapa_execucao:
                    etapa_execucao.status = 'APROVADO'
                    etapa_execucao.aprovado_em = utcnow_naive()
                    etapa_execucao.comentario = comentario
                    etapa_execucao.modificado_por = actor_id
                    etapa_execucao.modificado_em = utcnow_naive()
                    db.session.add(etapa_execucao)

                WorkflowService._registrar_assinatura_formal(
                    aprovacao=aprovacao,
                    assinatura_path=assinatura_path,
                    ip=ip,
                    user_agent=user_agent,
                    hash_doc=hash_doc,
                )

                AuditoriaService.registrar_auditoria_entidade(
                    acao='SIGN' if acao == 'SIGN' else 'APPROVE',
                    entidade='RDOAprovacao',
                    entidade_id=aprovacao.id,
                    depois=safe_model_to_dict(aprovacao),
                    payload={'comentario': comentario, 'assinatura_path': assinatura_path},
                )

                if WorkflowService._todas_etapas_aprovadas(aprovacao.rdo_id):
                    WorkflowService._finalizar_aprovacao(aprovacao.rdo_id)

                WorkflowService._atualizar_status_execucao(aprovacao.rdo_id)

                if commit:
                    db.session.commit()
                else:
                    db.session.flush()

                if rdo.status == 'APROVADO':
                    return True, "Aprovação registrada. RDO bloqueado e versionado."
                return True, "Etapa aprovada com sucesso"

            if acao == 'REJECT':
                motivo_rejeicao = motivo or comentario
                aprovacao.status = 'REJEITADO'
                aprovacao.data_aprovacao = utcnow_naive()
                aprovacao.comentario = motivo_rejeicao
                aprovacao.endereco_ip = ip
                aprovacao.modificado_por = actor_id
                aprovacao.modificado_em = utcnow_naive()
                db.session.add(aprovacao)

                if etapa_execucao:
                    etapa_execucao.status = 'REJEITADO'
                    etapa_execucao.aprovado_em = utcnow_naive()
                    etapa_execucao.comentario = motivo_rejeicao
                    etapa_execucao.modificado_por = actor_id
                    etapa_execucao.modificado_em = utcnow_naive()
                    db.session.add(etapa_execucao)

                AuditoriaService.registrar_auditoria_entidade(
                    acao='REJECT',
                    entidade='RDOAprovacao',
                    entidade_id=aprovacao.id,
                    depois=safe_model_to_dict(aprovacao),
                    payload={'motivo': motivo_rejeicao, 'reabrir': reabrir},
                )

                if workflow and workflow.rejeicao_cancela_fluxo:
                    WorkflowService._cancelar_fluxo(rdo.id, motivo_rejeicao, aprovacao.id)

                if reabrir and (workflow is None or workflow.permite_reabertura):
                    rdo.status = 'RASCUNHO'
                    rdo.modificado_por = actor_id
                    rdo.modificado_em = utcnow_naive()
                    db.session.add(rdo)
                    execucao = WorkflowService.obter_execucao_ativa(rdo.id)
                    if execucao:
                        execucao.status = 'REABERTO'
                        execucao.modificado_por = actor_id
                        execucao.modificado_em = utcnow_naive()
                        db.session.add(execucao)
                else:
                    rdo.status = 'REJEITADO'
                    rdo.modificado_por = actor_id
                    rdo.modificado_em = utcnow_naive()
                    db.session.add(rdo)

                WorkflowService._atualizar_status_execucao(aprovacao.rdo_id)

                if commit:
                    db.session.commit()
                else:
                    db.session.flush()
                return True, "Etapa rejeitada" + (" e RDO reaberto" if reabrir else "")

            return False, "Ação de workflow inválida"
        except Exception as exc:
            db.session.rollback()
            return False, str(exc)

    @staticmethod
    def aprovar_etapa(
        aprovacao_id: int,
        comentario: Optional[str] = None,
        ip: Optional[str] = None,
        hash_doc: Optional[str] = None,
        commit: bool = True,
    ) -> Tuple[bool, str]:
        return WorkflowService.processar_acao(
            aprovacao_id=aprovacao_id,
            acao='APPROVE',
            comentario=comentario,
            ip=ip,
            hash_doc=hash_doc,
            commit=commit,
        )

    @staticmethod
    def assinar_etapa(
        aprovacao_id: int,
        assinatura_path: str,
        ip: Optional[str] = None,
        hash_doc: Optional[str] = None,
        user_agent: Optional[str] = None,
        comentario: Optional[str] = None,
        commit: bool = True,
    ) -> Tuple[bool, str]:
        return WorkflowService.processar_acao(
            aprovacao_id=aprovacao_id,
            acao='SIGN',
            comentario=comentario,
            ip=ip,
            hash_doc=hash_doc,
            assinatura_path=assinatura_path,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def rejeitar_etapa(
        aprovacao_id: int,
        motivo: Optional[str] = None,
        ip: Optional[str] = None,
        reabrir: bool = False,
        commit: bool = True,
    ) -> Tuple[bool, str]:
        return WorkflowService.processar_acao(
            aprovacao_id=aprovacao_id,
            acao='REJECT',
            motivo=motivo,
            ip=ip,
            reabrir=reabrir,
            commit=commit,
        )

    @staticmethod
    def _finalizar_aprovacao(rdo_id: int) -> None:
        rdo = db.session.get(RDO, rdo_id)
        if not rdo:
            return

        actor_id = WorkflowService._ator_id()
        rdo.status = 'APROVADO'
        rdo.bloqueado_em = utcnow_naive()
        rdo.bloqueado_por = actor_id
        rdo.modificado_por = actor_id
        rdo.modificado_em = utcnow_naive()
        db.session.add(rdo)

        execucao = WorkflowService.obter_execucao_ativa(rdo_id)
        if execucao:
            execucao.status = 'APROVADO'
            execucao.etapa_atual_nivel = None
            execucao.finalizado_em = utcnow_naive()
            execucao.modificado_por = actor_id
            execucao.modificado_em = utcnow_naive()
            db.session.add(execucao)

        snapshot_data = safe_model_to_dict(rdo)
        versao = RDOVersao(
            empresa_id=rdo.empresa_id,
            rdo_id=rdo.id,
            numero_versao=rdo.versao,
            motivo='APROVADO_FINAL',
            dados_snapshot={
                'rdo': snapshot_data,
                'workflow_execucao': safe_model_to_dict(execucao) if execucao else None,
                'workflow_snapshot': execucao.workflow_snapshot if execucao else None,
            },
            criado_por=actor_id,
        )
        db.session.add(versao)
        rdo.versao += 1

        AuditoriaService.registrar_auditoria_entidade(
            acao='FINALIZAR_APROVACAO',
            entidade='RDO',
            entidade_id=rdo.id,
            depois=safe_model_to_dict(rdo),
            payload={'tem_execucao_workflow': bool(execucao)},
        )

    @staticmethod
    def _cancelar_fluxo(
        rdo_id: int,
        motivo: Optional[str] = None,
        aprovacao_executada_id: Optional[int] = None,
    ) -> None:
        actor_id = WorkflowService._ator_id()
        pendentes = RDOAprovacao.query.filter_by(
            rdo_id=rdo_id,
            status='PENDENTE',
            ativo=True,
        ).all()
        for aprov in pendentes:
            if aprovacao_executada_id and aprov.id == aprovacao_executada_id:
                continue
            aprov.status = 'CANCELADO'
            aprov.data_aprovacao = utcnow_naive()
            aprov.comentario = motivo or 'Fluxo cancelado por rejeição anterior'
            aprov.modificado_por = actor_id
            aprov.modificado_em = utcnow_naive()
            db.session.add(aprov)

        execucao = WorkflowService.obter_execucao_ativa(rdo_id)
        if execucao:
            for etapa in WorkflowExecucaoEtapa.query.filter_by(
                execucao_id=execucao.id,
                ativo=True,
                status='PENDENTE',
            ).all():
                etapa.status = 'CANCELADO'
                etapa.comentario = motivo or 'Fluxo cancelado por rejeição anterior'
                etapa.modificado_por = actor_id
                etapa.modificado_em = utcnow_naive()
                db.session.add(etapa)
            execucao.status = 'CANCELADO'
            execucao.modificado_por = actor_id
            execucao.modificado_em = utcnow_naive()
            db.session.add(execucao)

    # =========================================================================
    # BLOQUEIO PÓS-APROVAÇÃO
    # =========================================================================

    @staticmethod
    def pode_editar_rdo(rdo_id: int) -> Tuple[bool, str]:
        rdo = db.session.get(RDO, rdo_id)
        if not rdo:
            return False, "RDO não encontrado"
        if rdo.status == 'APROVADO':
            return False, "RDO foi aprovado e está bloqueado para edição"
        if rdo.status == 'REJEITADO':
            return False, "RDO foi rejeitado"
        if rdo.status == 'CANCELADO':
            return False, "RDO foi cancelado"
        return True, ""

    # =========================================================================
    # CONSULTAS DE STATUS
    # =========================================================================

    @staticmethod
    def obter_progresso_aprovacao(rdo_id: int) -> Dict[str, Any]:
        aprovacoes = RDOAprovacao.query.filter_by(
            rdo_id=rdo_id,
            ativo=True,
        ).order_by(RDOAprovacao.nivel.asc(), RDOAprovacao.id.asc()).all()
        execucao = WorkflowService.obter_execucao_ativa(rdo_id)

        return {
            'total': len(aprovacoes),
            'aprovadas': sum(1 for a in aprovacoes if a.status == 'APROVADO'),
            'rejeitadas': sum(1 for a in aprovacoes if a.status == 'REJEITADO'),
            'canceladas': sum(1 for a in aprovacoes if a.status == 'CANCELADO'),
            'pendentes': sum(1 for a in aprovacoes if a.status == 'PENDENTE'),
            'workflow_execucao_id': execucao.id if execucao else None,
            'workflow_status': execucao.status if execucao else None,
            'detalhes': [
                {
                    'id': a.id,
                    'nivel': a.nivel,
                    'aprovador': a.aprovador.nome if a.aprovador else 'N/A',
                    'status': a.status,
                    'data': a.data_aprovacao.isoformat() if a.data_aprovacao else None,
                    'comentario': a.comentario,
                }
                for a in aprovacoes
            ],
        }

    @staticmethod
    def obter_aprovacoes_pendentes(usuario_id: int, empresa_id: int) -> List[Dict[str, Any]]:
        aprovacoes = RDOAprovacao.query.filter_by(
            aprovador_id=usuario_id,
            status='PENDENTE',
            ativo=True,
        ).join(RDO).filter(
            RDO.empresa_id == empresa_id,
        ).all()

        return [
            {
                'id': a.id,
                'rdo_id': a.rdo_id,
                'rdo_data': a.rdo.data_rdo.isoformat() if a.rdo.data_rdo else None,
                'obra_nome': a.rdo.obra.nome if a.rdo.obra else 'N/A',
                'nivel': a.nivel,
                'criado_em': a.criado_em.isoformat(),
            }
            for a in aprovacoes
        ]

    @staticmethod
    def calcular_sla(etapa: WorkflowEtapa, criado_em: Any) -> Dict[str, Any]:
        if not etapa.sla_horas:
            return {'sla_horas': None, 'vencimento': None, 'vencido': False}

        vencimento = criado_em + timedelta(hours=etapa.sla_horas)
        agora = utcnow_naive()
        vencido = agora > vencimento

        return {
            'sla_horas': etapa.sla_horas,
            'vencimento': vencimento.isoformat(),
            'vencido': vencido,
            'tempo_restante_horas': (vencimento - agora).total_seconds() / 3600 if not vencido else 0,
        }
