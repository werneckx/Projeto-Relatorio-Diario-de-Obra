"""
Serviço centralizado de resolução e execução de workflows de aprovação.

Responsabilidades:
- Resolver workflow aplicável (empresa/obra)
- Gerar aprovações por etapas (sequencial/paralela)
- Registrar aprovações/rejeições
- Bloquear edição pós-aprovação final
- Versionar RDO aprovado
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple
from flask_login import current_user

from app import db
from app.models.workflow import WorkflowDefinicao, WorkflowEtapa
from app.models.rdo import RDO, RDOAprovacao, RDOVersao
from app.models.usuario import Usuario
from app.services.auditoria_service import AuditoriaService
from app.utils.datetime_utils import utcnow_naive
from app.utils.serializers import safe_model_to_dict


class WorkflowResolucaoError(Exception):
    """Erro ao resolver workflow."""
    pass


class WorkflowService:
    """Serviço centralizado de workflow."""

    # =========================================================================
    # RESOLUÇÃO DE WORKFLOW
    # =========================================================================

    @staticmethod
    def resolver_workflow(
        empresa_id: int,
        obra_id: int,
    ) -> Optional[WorkflowDefinicao]:
        """
        Resolve o workflow aplicável por empresa/obra (prioridade obra).
        
        Prioridade:
        1. Workflow específico da obra
        2. Workflow da empresa (obra_id=None)
        3. None se nenhum ativo
        """
        # Tenta workflow específico da obra
        workflow = WorkflowDefinicao.query.filter_by(
            empresa_id=empresa_id,
            obra_id=obra_id,
            ativo=True,
        ).first()

        if workflow:
            return workflow

        # Tenta workflow genérico da empresa
        workflow = WorkflowDefinicao.query.filter_by(
            empresa_id=empresa_id,
            obra_id=None,
            ativo=True,
        ).first()

        return workflow

    @staticmethod
    def obter_etapas_ordenadas(workflow_id: int) -> List[WorkflowEtapa]:
        """Obtém etapas do workflow ordenadas por nível."""
        return WorkflowEtapa.query.filter_by(
            workflow_id=workflow_id,
            ativo=True,
        ).order_by(WorkflowEtapa.nivel).all()

    # =========================================================================
    # GERAÇÃO DE APROVAÇÕES
    # =========================================================================

    @staticmethod
    def gerar_aprovacoes_por_etapas(
        rdo_id: int,
        workflow_id: int,
    ) -> List[RDOAprovacao]:
        """
        Gera aprovações por etapas do workflow.
        
        Retorna lista de RDOAprovacao criadas (não commitadas).
        """
        rdo = RDO.query.get(rdo_id)
        if not rdo:
            raise WorkflowResolucaoError(f"RDO {rdo_id} não encontrado")

        workflow = WorkflowDefinicao.query.get(workflow_id)
        if not workflow:
            raise WorkflowResolucaoError(f"Workflow {workflow_id} não encontrado")

        etapas = WorkflowService.obter_etapas_ordenadas(workflow_id)
        if not etapas:
            raise WorkflowResolucaoError(f"Workflow {workflow_id} não possui etapas ativas")

        aprovacoes_criadas: List[RDOAprovacao] = []

        if workflow.aprovacao_paralela:
            # PARALELA: todas as etapas no mesmo nível
            aprovacoes_criadas = WorkflowService._gerar_aprovacoes_paralelas(
                rdo, etapas
            )
        else:
            # SEQUENCIAL: etapas por ordem de nível
            aprovacoes_criadas = WorkflowService._gerar_aprovacoes_sequenciais(
                rdo, etapas
            )

        return aprovacoes_criadas

    @staticmethod
    def _gerar_aprovacoes_sequenciais(
        rdo: RDO,
        etapas: List[WorkflowEtapa],
    ) -> List[RDOAprovacao]:
        """Gera aprovações sequenciais (uma etapa por vez)."""
        aprovacoes = []

        for etapa in etapas:
            aprovador_id = WorkflowService._resolver_aprovador(etapa)
            if not aprovador_id:
                raise WorkflowResolucaoError(
                    f"Etapa {etapa.id} não possui aprovador definido"
                )

            aprov = RDOAprovacao(
                empresa_id=rdo.empresa_id,
                rdo_id=rdo.id,
                aprovador_id=aprovador_id,
                nivel=etapa.nivel,
                status='PENDENTE',
                criado_por=current_user.id if current_user else None,
            )
            db.session.add(aprov)
            aprovacoes.append(aprov)

        return aprovacoes

    @staticmethod
    def _gerar_aprovacoes_paralelas(
        rdo: RDO,
        etapas: List[WorkflowEtapa],
    ) -> List[RDOAprovacao]:
        """Gera aprovações paralelas (todas no mesmo nível)."""
        aprovacoes = []

        for etapa in etapas:
            aprovador_id = WorkflowService._resolver_aprovador(etapa)
            if not aprovador_id:
                raise WorkflowResolucaoError(
                    f"Etapa {etapa.id} não possui aprovador definido"
                )

            # Aprovação paralela: todas tem nível 1 (ou mesma ordem)
            aprov = RDOAprovacao(
                empresa_id=rdo.empresa_id,
                rdo_id=rdo.id,
                aprovador_id=aprovador_id,
                nivel=1,  # Paralelo: todos no nível 1
                status='PENDENTE',
                criado_por=current_user.id if current_user else None,
            )
            db.session.add(aprov)
            aprovacoes.append(aprov)

        return aprovacoes

    @staticmethod
    def _resolver_aprovador(etapa: WorkflowEtapa) -> Optional[int]:
        """
        Resolve o aprovador de uma etapa.
        
        Prioridade:
        1. Usuário específico (usuario_aprovador_id)
        2. Papel (papel_id)
        3. None
        """
        if etapa.usuario_aprovador_id:
            return etapa.usuario_aprovador_id

        if etapa.papel_id:
            # Tenta encontrar um usuário com esse papel
            usuario = Usuario.query.join(
                Usuario.papeis
            ).filter(
                Usuario.empresa_id == etapa.empresa_id,
                Usuario.ativo == True,
            ).first()
            if usuario:
                return usuario.id

        return None

    # =========================================================================
    # APROVAÇÃO/REJEIÇÃO
    # =========================================================================

    @staticmethod
    def aprovar_etapa(
        aprovacao_id: int,
        comentario: Optional[str] = None,
        ip: Optional[str] = None,
        hash_doc: Optional[str] = None,
        commit: bool = True,
    ) -> Tuple[bool, str]:
        """
        Aprova uma etapa do RDO.
        
        Retorna:
        - (True, "mensagem") se sucesso
        - (False, "erro") se falha
        
        Se todas as etapas forem aprovadas, bloqueia RDO e cria versão.
        """
        try:
            aprovacao = RDOAprovacao.query.get(aprovacao_id)
            if not aprovacao:
                return False, "Aprovação não encontrada"

            if aprovacao.status != 'PENDENTE':
                return False, f"Aprovação já foi {aprovacao.status.lower()}"

            # Marcar como aprovado
            aprovacao.status = 'APROVADO'
            aprovacao.data_aprovacao = utcnow_naive()
            aprovacao.comentario = comentario
            aprovacao.endereco_ip = ip
            aprovacao.hash = hash_doc
            aprovacao.modificado_por = current_user.id if current_user else None
            aprovacao.modificado_em = utcnow_naive()

            db.session.add(aprovacao)
            db.session.flush()

            # Registra auditoria
            AuditoriaService.registrar_auditoria_entidade(
                acao='APPROVE',
                entidade='RDOAprovacao',
                entidade_id=aprovacao.id,
                depois=safe_model_to_dict(aprovacao),
                payload={'comentario': comentario},
            )

            finalizou = False
            if WorkflowService._todas_etapas_aprovadas(aprovacao.rdo_id):
                WorkflowService._finalizar_aprovacao(aprovacao.rdo_id)
                finalizou = True

            # Persistência necessária para testes que chamam refresh logo após a execução.
            if commit:
                db.session.commit()
            else:
                db.session.flush()

            if finalizou:
                return True, "Aprovação registrada. RDO bloqueado e versionado."

            return True, "Etapa aprovada com sucesso"
        except Exception as e:
            db.session.rollback()
            return False, str(e)


    @staticmethod
    def rejeitar_etapa(
        aprovacao_id: int,
        motivo: Optional[str] = None,
        ip: Optional[str] = None,
        reabrir: bool = False,
        commit: bool = True,
    ) -> Tuple[bool, str]:
        """
        Rejeita uma etapa do RDO.
        
        Se reabrir=False e rejeicao_cancela_fluxo=True:
        - Cancela todas as outras aprovações pendentes
        
        Se reabrir=True:
        - Permite que o RDO seja retornado para RASCUNHO
        """
        try:
            aprovacao = RDOAprovacao.query.get(aprovacao_id)
            if not aprovacao:
                return False, "Aprovação não encontrada"

            if aprovacao.status != 'PENDENTE':
                return False, f"Aprovação já foi {aprovacao.status.lower()}"

            rdo = RDO.query.get(aprovacao.rdo_id)
            workflow = WorkflowService.resolver_workflow(rdo.empresa_id, rdo.obra_id) if rdo else None

            # Marcar como rejeitado
            aprovacao.status = 'REJEITADO'
            aprovacao.data_aprovacao = utcnow_naive()
            aprovacao.comentario = motivo
            aprovacao.endereco_ip = ip
            aprovacao.modificado_por = current_user.id if current_user else None
            aprovacao.modificado_em = utcnow_naive()

            db.session.add(aprovacao)

            # Registra auditoria
            AuditoriaService.registrar_auditoria_entidade(
                acao='REJECT',
                entidade='RDOAprovacao',
                entidade_id=aprovacao.id,
                depois=safe_model_to_dict(aprovacao),
                payload={'motivo': motivo, 'reabrir': reabrir},
            )

            # Segundo configuração, cancela fluxo
            if workflow and workflow.rejeicao_cancela_fluxo and rdo:
                WorkflowService._cancelar_fluxo(rdo.id, motivo)

            if reabrir and rdo:
                # Retorna RDO para RASCUNHO
                rdo.status = 'RASCUNHO'
                rdo.modificado_por = current_user.id if current_user else None
                rdo.modificado_em = utcnow_naive()
                db.session.add(rdo)

                AuditoriaService.registrar_auditoria_entidade(
                    acao='REABRIR',
                    entidade='RDO',
                    entidade_id=rdo.id,
                    depois=safe_model_to_dict(rdo),
                )

            if commit:
                db.session.commit()
            else:
                db.session.flush()

            return True, "Etapa rejeitada" + (" e RDO reabrido" if reabrir else "")
        except Exception as e:
            db.session.rollback()
            return False, str(e)


    @staticmethod
    def _todas_etapas_aprovadas(rdo_id: int) -> bool:
        """Verifica se todas as aprovações pendentes foram realizadas."""
        pendentes = RDOAprovacao.query.filter_by(
            rdo_id=rdo_id,
            status='PENDENTE',
            ativo=True,
        ).count()
        return pendentes == 0

    @staticmethod
    def _finalizar_aprovacao(rdo_id: int) -> None:
        """
        Finaliza aprovação:
        1. Bloqueia RDO (status=APROVADO)
        2. Cria versão do RDO
        """
        rdo = RDO.query.get(rdo_id)
        if not rdo:
            return

        # 1. Bloqueia RDO
        rdo.status = 'APROVADO'
        # Não alteramos FRENTE/TRABALHO aqui (FK NOT NULL em SQLite)
        rdo.bloqueado_em = utcnow_naive()
        rdo.bloqueado_por = current_user.id if current_user else None
        rdo.modificado_por = current_user.id if current_user else None
        rdo.modificado_em = utcnow_naive()

        db.session.add(rdo)

        # 2. Cria versão
        snapshot_data = safe_model_to_dict(rdo)
        versao = RDOVersao(
            empresa_id=rdo.empresa_id,
            rdo_id=rdo.id,
            numero_versao=rdo.versao,
            motivo='APROVADO_FINAL',
            dados_snapshot=snapshot_data,
            criado_por=current_user.id if current_user else None,
        )
        db.session.add(versao)

        # Incrementa versão do RDO
        rdo.versao += 1

        # Registra auditoria
        AuditoriaService.registrar_auditoria_entidade(
            acao='FINALIZAR_APROVACAO',
            entidade='RDO',
            entidade_id=rdo.id,
            depois=safe_model_to_dict(rdo),
            payload={'snapshot_versao': len(snapshot_data)},
        )

    @staticmethod
    def _cancelar_fluxo(rdo_id: int, motivo: Optional[str] = None) -> None:
        """Cancela todas as aprovações pendentes."""
        pendentes = RDOAprovacao.query.filter_by(
            rdo_id=rdo_id,
            status='PENDENTE',
            ativo=True,
        ).all()

        for aprov in pendentes:
            aprov.status = 'CANCELADO'
            aprov.data_aprovacao = utcnow_naive()
            aprov.comentario = motivo or 'Fluxo cancelado por rejeição anterior'
            aprov.modificado_por = current_user.id if current_user else None
            aprov.modificado_em = utcnow_naive()
            db.session.add(aprov)

    # =========================================================================
    # BLOQUEIO PÓS-APROVAÇÃO
    # =========================================================================

    @staticmethod
    def pode_editar_rdo(rdo_id: int) -> Tuple[bool, str]:
        """
        Verifica se um RDO pode ser editado.
        
        Retorna (True, "") se pode editar.
        Retorna (False, motivo) se não pode editar.
        """
        rdo = RDO.query.get(rdo_id)
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
        """Retorna progresso da aprovação do RDO."""
        aprovacoes = RDOAprovacao.query.filter_by(
            rdo_id=rdo_id,
            ativo=True,
        ).order_by(RDOAprovacao.nivel).all()

        return {
            'total': len(aprovacoes),
            'aprovadas': sum(1 for a in aprovacoes if a.status == 'APROVADO'),
            'rejeitadas': sum(1 for a in aprovacoes if a.status == 'REJEITADO'),
            'canceladas': sum(1 for a in aprovacoes if a.status == 'CANCELADO'),
            'pendentes': sum(1 for a in aprovacoes if a.status == 'PENDENTE'),
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
        """Lista aprovações pendentes para um usuário."""
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
    def calcular_sla(etapa: WorkflowEtapa, criado_em: datetime) -> Dict[str, Any]:
        """Calcula SLA de uma etapa."""
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
