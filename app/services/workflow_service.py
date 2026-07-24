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

import json
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask_login import current_user

from app import db
from app.models.configuracao import ObraConfig
from app.models.obra import Obra, ObraUsuario
from app.models.rdo import RDO, RDOAprovacao, RDOAssinatura, RDOVersao
from app.models.usuario import Papel, PapelPermissao, Permissao, Usuario, UsuarioPapel
from app.models.workflow import (
    WorkflowDefinicao,
    WorkflowEtapa,
    WorkflowExecucao,
    WorkflowExecucaoEtapa,
    WorkflowGrupo,
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
    WORKFLOW_DEFAULT_CONFIG_KEY = 'workflow.default'
    WORKFLOW_ASSIGNMENTS_CONFIG_KEY = 'workflow.assignments'
    WORKFLOW_APPROVAL_PERMISSION_KEYS = {
        'rdo.view': 'Visualizar RDOs',
        'rdo.approve': 'Aprovar ou rejeitar RDOs',
        'rdo.sign': 'Assinar RDOs',
        'workflow.view': 'Visualizar workflows',
        'workflow.approve': 'Aprovar documentos em workflow',
        'workflow.reject': 'Reprovar documentos em workflow',
        'workflow.sign': 'Assinar documentos em workflow',
    }

    @staticmethod
    def _resumo_comportamento_workflow(workflow: WorkflowDefinicao) -> str:
        tipo_fluxo = (workflow.tipo_fluxo or 'CONFIGURAVEL').upper()
        if tipo_fluxo == 'SIMPLES':
            return 'Fluxo enxuto com uma unica aprovacao obrigatoria.'
        if tipo_fluxo == 'SEQUENCIAL':
            return 'As etapas seguem uma ordem hierarquica, uma apos a outra.'
        if tipo_fluxo == 'PARALELO':
            return 'Todos os responsaveis do grupo recebem a etapa ao mesmo tempo.'
        if tipo_fluxo == 'MATRIZ':
            return 'O aprovador e resolvido conforme o papel configurado para a obra.'
        if tipo_fluxo == 'CLIENTE_INTERNA':
            return 'O fluxo percorre etapas internas e pode finalizar com aceite do cliente.'
        return 'Fluxo configuravel com etapas, papeis e paralelismo definidos pela empresa ou pela obra.'

    @staticmethod
    def _montar_diagrama_preview_workflow(workflow: WorkflowDefinicao, etapas: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        etapas_lista = list(etapas or [])
        is_parallel = bool(workflow.aprovacao_paralela)
        has_parallel_group = any(etapa.get('grupo_paralelo') not in (None, '', 0) for etapa in etapas_lista)

        rows: List[Dict[str, Any]] = []
        if is_parallel:
            rows.append({
                'kind': 'parallel',
                'title': 'Aprovacao Paralela',
                'subtitle': 'Todos recebem esta solicitacao ao mesmo tempo.',
                'items': etapas_lista,
            })
        elif has_parallel_group:
            grouped: Dict[Any, List[Dict[str, Any]]] = {}
            sequenciais: List[Dict[str, Any]] = []
            for etapa in etapas_lista:
                grupo = etapa.get('grupo_paralelo')
                if grupo in (None, '', 0):
                    sequenciais.append(etapa)
                    continue
                grouped.setdefault(grupo, []).append(etapa)

            for etapa in sequenciais:
                rows.append({
                    'kind': 'single',
                    'title': etapa.get('nome') or 'Etapa',
                    'subtitle': 'Etapa sequencial.',
                    'items': [etapa],
                })

            for grupo, itens in sorted(grouped.items(), key=lambda item: item[0]):
                itens_ordenados = sorted(itens, key=lambda etapa: (etapa.get('nivel') or 0, etapa.get('nome') or ''))
                rows.append({
                    'kind': 'parallel',
                    'title': f'Grupo paralelo {grupo}',
                    'subtitle': 'As etapas deste grupo disparam juntas.',
                    'items': itens_ordenados,
                })
        else:
            for etapa in etapas_lista:
                rows.append({
                    'kind': 'single',
                    'title': etapa.get('nome') or 'Etapa',
                    'subtitle': 'Etapa sequencial.',
                    'items': [etapa],
                })

        return {
            'tipo_fluxo': workflow.tipo_fluxo or 'CONFIGURAVEL',
            'resumo': WorkflowService._resumo_comportamento_workflow(workflow),
            'rows': rows,
        }

    @staticmethod
    def _order_by_nullable_asc(column):
        """Compatível com MySQL: mantém nulos por último."""
        return (column.is_(None), column.asc())

    @staticmethod
    def _order_by_nullable_desc(column):
        """Compatível com MySQL: prioriza não nulos em ordem decrescente."""
        return (column.is_(None), column.desc())

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
    def _resolver_workflow_por_referencia(
        empresa_id: int,
        referencia: Optional[str],
        obra_id: Optional[int] = None,
        incluir_workflows_obra: bool = False,
    ) -> Optional[WorkflowDefinicao]:
        referencia_normalizada = str(referencia or '').strip()
        if not referencia_normalizada:
            return None

        query = WorkflowDefinicao.query.filter(
            WorkflowDefinicao.empresa_id == empresa_id,
            WorkflowDefinicao.ativo.is_(True),
        )
        if incluir_workflows_obra:
            if obra_id is not None:
                query = query.filter(
                    db.or_(
                        WorkflowDefinicao.obra_id.is_(None),
                        WorkflowDefinicao.obra_id == obra_id,
                    )
                )
        else:
            query = query.filter(WorkflowDefinicao.obra_id.is_(None))

        referencia_lower = referencia_normalizada.lower()
        workflow_id = None
        if referencia_lower.startswith('id:'):
            try:
                workflow_id = int(referencia_normalizada.split(':', 1)[1].strip())
            except (TypeError, ValueError):
                workflow_id = None
        elif referencia_normalizada.isdigit():
            workflow_id = int(referencia_normalizada)

        if workflow_id:
            return query.filter(WorkflowDefinicao.id == workflow_id).order_by(WorkflowDefinicao.id.asc()).first()

        return query.filter(
            db.or_(
                db.func.upper(db.func.trim(WorkflowDefinicao.codigo)) == referencia_normalizada.upper(),
                db.func.upper(db.func.trim(WorkflowDefinicao.nome)) == referencia_normalizada.upper(),
            )
        ).order_by(WorkflowDefinicao.id.asc()).first()

    @staticmethod
    def _resolver_workflow_obra_por_configuracao(
        empresa_id: int,
        obra_id: Optional[int],
    ) -> Optional[WorkflowDefinicao]:
        if obra_id is None:
            return None

        config = ObraConfig.query.filter_by(
            empresa_id=empresa_id,
            obra_id=obra_id,
            chave=WorkflowService.WORKFLOW_DEFAULT_CONFIG_KEY,
        ).first()
        if not config or not str(config.valor or '').strip():
            return None

        return WorkflowService._resolver_workflow_por_referencia(
            empresa_id=empresa_id,
            referencia=config.valor,
            obra_id=obra_id,
            incluir_workflows_obra=True,
        )

    @staticmethod
    def _resolver_workflow_empresa_padrao(empresa_id: int) -> Optional[WorkflowDefinicao]:
        try:
            codigo_padrao = ConfigService.obter_valor(
                empresa_id=empresa_id,
                obra_id=None,
                chave=WorkflowService.WORKFLOW_DEFAULT_CONFIG_KEY,
            )
        except Exception:
            codigo_padrao = None

        workflow = WorkflowService._resolver_workflow_por_referencia(
            empresa_id=empresa_id,
            referencia=codigo_padrao or WorkflowService.DEFAULT_WORKFLOW_CODIGO,
            incluir_workflows_obra=False,
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

        workflow = WorkflowService._resolver_workflow_obra_por_configuracao(empresa_id, obra_id)
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
            *WorkflowService._order_by_nullable_asc(WorkflowEtapa.ordem),
            WorkflowEtapa.id.asc(),
        ).all()

    @staticmethod
    def obter_execucao_ativa(rdo_id: int) -> Optional[WorkflowExecucao]:
        return WorkflowExecucao.query.filter_by(
            rdo_id=rdo_id,
            ativo=True,
        ).order_by(WorkflowExecucao.id.desc()).first()

    @staticmethod
    def listar_workflows_disponiveis_obra(
        empresa_id: int,
        obra_id: Optional[int] = None,
    ) -> List[WorkflowDefinicao]:
        query = WorkflowDefinicao.query.filter(
            WorkflowDefinicao.empresa_id == empresa_id,
            WorkflowDefinicao.ativo.is_(True),
        )
        if obra_id is not None:
            query = query.filter(
                db.or_(
                    WorkflowDefinicao.obra_id.is_(None),
                    WorkflowDefinicao.obra_id == obra_id,
                )
            )
        else:
            query = query.filter(WorkflowDefinicao.obra_id.is_(None))

        return query.order_by(
            WorkflowDefinicao.obra_id.isnot(None).desc(),
            WorkflowDefinicao.nome.asc(),
            WorkflowDefinicao.id.asc(),
        ).all()

    @staticmethod
    def _obter_workflow_assignments_payload(
        empresa_id: int,
        obra_id: Optional[int],
    ) -> Dict[str, Any]:
        if not empresa_id or not obra_id:
            return {}

        row = ObraConfig.query.filter_by(
            empresa_id=empresa_id,
            obra_id=obra_id,
            chave=WorkflowService.WORKFLOW_ASSIGNMENTS_CONFIG_KEY,
        ).first()
        if not row or not row.valor:
            return {}

        try:
            payload = json.loads(row.valor) if isinstance(row.valor, str) else row.valor
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _obter_assignment_usuario_id(
        empresa_id: int,
        obra_id: Optional[int],
        workflow_id: Optional[int],
        etapa_id: Optional[int],
    ) -> Optional[int]:
        if not workflow_id or not etapa_id or not obra_id:
            return None

        payload = WorkflowService._obter_workflow_assignments_payload(empresa_id, obra_id)
        payload_workflow_id = payload.get('workflow_id')
        if payload_workflow_id not in (workflow_id, str(workflow_id)):
            return None

        assignments = payload.get('assignments') or {}
        if not isinstance(assignments, dict):
            return None

        raw_value = assignments.get(str(etapa_id), assignments.get(etapa_id))
        try:
            return int(raw_value) if raw_value not in (None, '') else None
        except (TypeError, ValueError):
            return None

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
        ).order_by(*WorkflowService._order_by_nullable_desc(Papel.empresa_id), Papel.id.asc()).first()

    @staticmethod
    def _papel_resolvido_etapa(etapa: WorkflowEtapa) -> Optional[Papel]:
        papel = etapa.papel
        if papel is None and etapa.papel_codigo:
            papel = WorkflowService._resolver_papel_por_codigo(etapa.empresa_id, etapa.papel_codigo)
        if papel is None and etapa.tipo_aprovador == 'CLIENTE':
            papel = WorkflowService._resolver_papel_por_codigo(etapa.empresa_id, 'CLIENTE_OBRA')
        return papel

    @staticmethod
    def _usuarios_elegiveis_etapa(
        empresa_id: int,
        obra_id: int,
        etapa: WorkflowEtapa,
    ) -> List[ObraUsuario]:
        query = (
            db.session.query(ObraUsuario)
            .join(Usuario, Usuario.id == ObraUsuario.usuario_id)
            .filter(
                ObraUsuario.empresa_id == empresa_id,
                ObraUsuario.obra_id == obra_id,
                ObraUsuario.ativo.is_(True),
                Usuario.ativo.is_(True),
            )
        )

        if etapa.tipo_aprovador == 'USUARIO' and etapa.usuario_aprovador_id:
            query = query.filter(ObraUsuario.usuario_id == etapa.usuario_aprovador_id)
            return query.order_by(ObraUsuario.id.asc()).all()

        if etapa.tipo_aprovador == 'RESPONSAVEL_OBRA':
            obra = db.session.get(Obra, obra_id)
            if not obra or not obra.usuario_responsavel_id:
                return []
            query = query.filter(ObraUsuario.usuario_id == obra.usuario_responsavel_id)
            return query.order_by(ObraUsuario.id.asc()).all()

        papel = WorkflowService._papel_resolvido_etapa(etapa)
        papel_id = papel.id if papel else etapa.papel_id
        if papel_id:
            query = query.filter(ObraUsuario.papel_id == papel_id)
        else:
            return []

        return query.order_by(ObraUsuario.id.asc()).all()

    @staticmethod
    def _usuarios_fallback_empresa(
        empresa_id: int,
    ) -> List[Usuario]:
        return (
            Usuario.query
            .filter(
                Usuario.empresa_id == empresa_id,
                Usuario.ativo.is_(True),
            )
            .order_by(Usuario.email.asc(), Usuario.id.asc())
            .all()
        )

    @staticmethod
    def _usuario_elegivel_para_etapa(
        empresa_id: int,
        obra_id: int,
        etapa: WorkflowEtapa,
        usuario_id: Optional[int],
    ) -> bool:
        if not usuario_id:
            return False

        usuario_id_int = int(usuario_id)
        if etapa.tipo_aprovador == 'USUARIO':
            return etapa.usuario_aprovador_id == usuario_id_int

        if etapa.tipo_aprovador == 'RESPONSAVEL_OBRA':
            obra = db.session.get(Obra, obra_id)
            return bool(obra and obra.usuario_responsavel_id == usuario_id_int)

        elegiveis = WorkflowService._usuarios_elegiveis_etapa(empresa_id, obra_id, etapa)
        if elegiveis:
            return any(rel.usuario_id == usuario_id_int for rel in elegiveis)

        usuario = db.session.get(Usuario, usuario_id_int)
        return bool(usuario and usuario.empresa_id == empresa_id and usuario.ativo)

    @staticmethod
    def _garantir_vinculo_obra_usuario(
        empresa_id: int,
        obra_id: int,
        usuario_id: int,
        papel_id: Optional[int],
    ) -> None:
        vinculo = ObraUsuario.query.filter_by(
            empresa_id=empresa_id,
            obra_id=obra_id,
            usuario_id=usuario_id,
        ).first()
        if not vinculo:
            vinculo = ObraUsuario(
                empresa_id=empresa_id,
                obra_id=obra_id,
                usuario_id=usuario_id,
                papel_id=papel_id,
                ativo=True,
            )
            db.session.add(vinculo)
        else:
            vinculo.ativo = True
            if papel_id:
                vinculo.papel_id = papel_id
            db.session.add(vinculo)

        db.session.flush()

    @staticmethod
    def _garantir_permissao_aprovacao(
        empresa_id: int,
        obra_id: int,
        usuario_id: int,
        papel_id: Optional[int],
    ) -> None:
        usuario = db.session.get(Usuario, usuario_id)
        if not usuario or not usuario.ativo:
            raise WorkflowResolucaoError(f'Usuário {usuario_id} inválido para aprovação.')

        papel_id_resolvido = papel_id
        if not papel_id_resolvido:
            usuario_papel_existente = UsuarioPapel.query.filter(
                UsuarioPapel.usuario_id == usuario_id,
                UsuarioPapel.ativo.is_(True),
                UsuarioPapel.empresa_id == empresa_id,
            ).order_by(UsuarioPapel.papel_id.asc()).first()
            papel_id_resolvido = usuario_papel_existente.papel_id if usuario_papel_existente else None

        if not papel_id_resolvido:
            raise WorkflowResolucaoError(f'Usuário {usuario.nome} não possui papel elegível para receber permissão de aprovação.')

        WorkflowService._garantir_vinculo_obra_usuario(
            empresa_id=empresa_id,
            obra_id=obra_id,
            usuario_id=usuario_id,
            papel_id=papel_id_resolvido,
        )

        usuario_papel = UsuarioPapel.query.filter_by(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            papel_id=papel_id_resolvido,
        ).first()
        if not usuario_papel:
            usuario_papel = UsuarioPapel(
                empresa_id=empresa_id,
                usuario_id=usuario_id,
                papel_id=papel_id_resolvido,
                ativo=True,
            )
            db.session.add(usuario_papel)
        else:
            usuario_papel.ativo = True
            db.session.add(usuario_papel)

        for chave, descricao in WorkflowService.WORKFLOW_APPROVAL_PERMISSION_KEYS.items():
            permissao = Permissao.query.filter(
                Permissao.chave == chave,
                Permissao.ativo.is_(True),
                db.or_(Permissao.empresa_id.is_(None), Permissao.empresa_id == empresa_id),
            ).order_by(*WorkflowService._order_by_nullable_desc(Permissao.empresa_id), Permissao.id.asc()).first()
            if not permissao:
                permissao = Permissao(
                    empresa_id=None,
                    chave=chave,
                    descricao=descricao,
                    is_system=True,
                    ativo=True,
                )
                db.session.add(permissao)
                db.session.flush()

            papel_perm = PapelPermissao.query.filter(
                PapelPermissao.papel_id == papel_id_resolvido,
                PapelPermissao.permissao_id == permissao.id,
            ).order_by(*WorkflowService._order_by_nullable_desc(PapelPermissao.empresa_id), PapelPermissao.id.asc()).first()
            if not papel_perm:
                papel_perm = PapelPermissao(
                    empresa_id=empresa_id,
                    papel_id=papel_id_resolvido,
                    permissao_id=permissao.id,
                    ativo=True,
                )
                db.session.add(papel_perm)
            else:
                papel_perm.ativo = True
                db.session.add(papel_perm)

        db.session.flush()

    @staticmethod
    def validar_configuracao_workflow_obra(
        empresa_id: int,
        obra_id: int,
        workflow_id: int,
        assignments: Optional[Dict[str, Any]] = None,
        auto_grant_signature: bool = False,
    ) -> Dict[str, Any]:
        workflow = db.session.get(WorkflowDefinicao, workflow_id)
        if not workflow or workflow.empresa_id != empresa_id or not workflow.ativo:
            raise WorkflowResolucaoError('Workflow selecionado é inválido para esta empresa.')

        if workflow.obra_id not in (None, obra_id):
            raise WorkflowResolucaoError('Workflow selecionado não pertence ao escopo desta obra.')

        obra = db.session.get(Obra, obra_id)
        if not obra or obra.empresa_id != empresa_id:
            raise WorkflowResolucaoError('Obra inválida para configuração do workflow.')

        assignments = assignments or {}
        etapas = WorkflowService.obter_etapas_ordenadas(workflow.id)
        etapas_resolvidas = []
        erros = []

        for etapa in etapas:
            papel = WorkflowService._papel_resolvido_etapa(etapa)
            papel_id = papel.id if papel else etapa.papel_id
            elegiveis = WorkflowService._usuarios_elegiveis_etapa(empresa_id, obra_id, etapa)
            fallback_usuarios = WorkflowService._usuarios_fallback_empresa(empresa_id) if not elegiveis else []
            selected_raw = assignments.get(str(etapa.id), assignments.get(etapa.id))
            selected_id = None
            if selected_raw not in (None, ''):
                try:
                    selected_id = int(selected_raw)
                except (TypeError, ValueError):
                    selected_id = None

            suggested_id = None
            if etapa.tipo_aprovador == 'USUARIO' and etapa.usuario_aprovador_id:
                suggested_id = etapa.usuario_aprovador_id
            elif etapa.tipo_aprovador == 'RESPONSAVEL_OBRA' and obra.usuario_responsavel_id:
                suggested_id = obra.usuario_responsavel_id
            elif elegiveis:
                suggested_id = elegiveis[0].usuario_id
            elif fallback_usuarios:
                suggested_id = fallback_usuarios[0].id

            if (
                auto_grant_signature
                and etapa.tipo_aprovador == 'PAPEL'
                and papel_id
                and not elegiveis
                and not selected_id
            ):
                papel_nome = papel.nome if papel else str(papel_id)
                erros.append(
                    f'A etapa "{etapa.nome}" usa o papel "{papel_nome}", mas nenhum usuario com este papel esta vinculado a obra. Vincule um usuario a obra antes de salvar o workflow.'
                )
                continue

            usuario_final_id = selected_id or suggested_id
            if not usuario_final_id:
                erros.append(f'A etapa "{etapa.nome}" não possui responsável elegível na obra.')
                continue

            if not WorkflowService._usuario_elegivel_para_etapa(empresa_id, obra_id, etapa, usuario_final_id):
                erros.append(f'O usuário selecionado para a etapa "{etapa.nome}" não possui o papel exigido.')
                continue

            usuario_final = db.session.get(Usuario, usuario_final_id)
            if not usuario_final or not usuario_final.ativo:
                erros.append(f'O responsável da etapa "{etapa.nome}" está inativo.')
                continue

            usuarios_disponiveis = [
                {
                    'id': rel.usuario_id,
                    'nome': rel.colaborador.nome if rel.colaborador else '',
                    'email': rel.colaborador.email if rel.colaborador else '',
                    'origem': 'obra',
                }
                for rel in elegiveis
            ]
            if not usuarios_disponiveis:
                usuarios_disponiveis = [
                    {
                        'id': usuario.id,
                        'nome': usuario.nome,
                        'email': usuario.email,
                        'origem': 'empresa',
                    }
                    for usuario in fallback_usuarios
                ]
                if not any(item['id'] == usuario_final.id for item in usuarios_disponiveis):
                    usuarios_disponiveis.append({
                        'id': usuario_final.id,
                        'nome': usuario_final.nome,
                        'email': usuario_final.email,
                        'origem': 'empresa',
                    })

            if auto_grant_signature:
                WorkflowService._garantir_permissao_aprovacao(empresa_id, obra_id, usuario_final_id, papel_id)

            etapas_resolvidas.append({
                'etapa_id': etapa.id,
                'workflow_id': workflow.id,
                'nivel': etapa.nivel,
                'nome': etapa.nome,
                'tipo_aprovador': etapa.tipo_aprovador,
                'papel_id': papel_id,
                'papel_nome': papel.nome if papel else None,
                'usuario_aprovador_id': etapa.usuario_aprovador_id,
                'workflow_group': etapa.grupo.ordem if etapa.grupo else (etapa.grupo_paralelo or etapa.nivel),
                'grupo_id': etapa.grupo_id,
                'grupo_paralelo': etapa.grupo_paralelo,
                'regra_etapa': 'PRIMEIRO' if etapa.grupo and etapa.grupo.regra_aprovacao == 'QUALQUER' else 'TODOS',
                'regra_aprovacao': etapa.grupo.regra_aprovacao if etapa.grupo and etapa.grupo.regra_aprovacao else 'TODOS',
                'assinatura_obrigatoria': bool(etapa.assinatura_obrigatoria),
                'usuario_id': usuario_final_id,
                'usuario_nome': usuario_final.nome,
                'usuario_email': usuario_final.email,
                'usuario_sugerido_id': suggested_id,
                'fallback_empresa': not bool(elegiveis),
                'usuarios_disponiveis': usuarios_disponiveis,
            })

        if erros:
            raise WorkflowResolucaoError(' '.join(erros))

        return {
            'workflow': workflow,
            'etapas': etapas_resolvidas,
            'assignments': {str(item['etapa_id']): item['usuario_id'] for item in etapas_resolvidas},
            'diagram': WorkflowService._montar_diagrama_preview_workflow(workflow, etapas_resolvidas),
        }

    @staticmethod
    def construir_preview_workflow_obra(
        empresa_id: int,
        obra_id: int,
        workflow_id: Optional[int] = None,
        assignments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        workflow = db.session.get(WorkflowDefinicao, workflow_id) if workflow_id else WorkflowService.resolver_workflow(empresa_id, obra_id)
        if not workflow:
            return {
                'workflow_id': None,
                'workflow_nome': 'Sem workflow',
                'workflow_origem': 'Sem workflow',
                'workflow_origem_tipo': 'indefinido',
                'etapas': [],
                'valid': False,
                'errors': ['Nenhum workflow ativo encontrado para a obra.'],
            }

        payload = assignments or WorkflowService._obter_workflow_assignments_payload(empresa_id, obra_id).get('assignments') or {}
        try:
            validado = WorkflowService.validar_configuracao_workflow_obra(
                empresa_id=empresa_id,
                obra_id=obra_id,
                workflow_id=workflow.id,
                assignments=payload,
                auto_grant_signature=False,
            )
            etapas = validado['etapas']
            errors = []
            valid = True
        except WorkflowResolucaoError as exc:
            etapas = [
                {
                    'etapa_id': etapa.id,
                    'workflow_id': workflow.id,
                    'nivel': etapa.nivel,
                    'ordem': etapa.ordem,
                    'nome': etapa.nome,
                    'tipo_aprovador': etapa.tipo_aprovador,
                    'papel_id': etapa.papel_id,
                    'papel_nome': etapa.papel.nome if etapa.papel else None,
                    'usuario_aprovador_id': etapa.usuario_aprovador_id,
                    'usuario_nome': etapa.usuario_aprovador.nome if etapa.usuario_aprovador else None,
                    'workflow_group': etapa.grupo.ordem if etapa.grupo else (etapa.grupo_paralelo or etapa.nivel),
                    'grupo_id': etapa.grupo_id,
                    'grupo_paralelo': etapa.grupo_paralelo,
                    'regra_etapa': 'PRIMEIRO' if etapa.grupo and etapa.grupo.regra_aprovacao == 'QUALQUER' else 'TODOS',
                    'regra_aprovacao': etapa.grupo.regra_aprovacao if etapa.grupo and etapa.grupo.regra_aprovacao else 'TODOS',
                    'assinatura_obrigatoria': bool(etapa.assinatura_obrigatoria),
                }
                for etapa in WorkflowService.obter_etapas_ordenadas(workflow.id)
            ]
            errors = [str(exc)]
            valid = False

        return {
            'workflow_id': workflow.id,
            'workflow_nome': workflow.nome,
            'workflow_codigo': workflow.codigo,
            'workflow_descricao': workflow.descricao,
            'tipo_fluxo': workflow.tipo_fluxo or 'CONFIGURAVEL',
            'aprovacao_paralela': bool(workflow.aprovacao_paralela),
            'workflow_origem': 'Workflow Próprio da Obra' if workflow.obra_id else 'Herdado da Empresa',
            'workflow_origem_tipo': 'obra' if workflow.obra_id else 'empresa',
            'etapas': etapas,
            'diagram': WorkflowService._montar_diagrama_preview_workflow(workflow, etapas),
            'valid': valid,
            'errors': errors,
        }

    def _resolver_aprovador(
        etapa: WorkflowEtapa,
        rdo: Optional[RDO] = None,
    ) -> Optional[int]:
        """
        Resolve o aprovador de uma etapa.

        Prioridade:
        1. Usuário específico
        2. Responsável da obra (quando aplicável)
        3. Papel alocado na obra via obra_usuario

        obra_usuario is the only official source for papel-based approvers.
        """
        if rdo:
            manual_assignment_id = WorkflowService._obter_assignment_usuario_id(
                empresa_id=etapa.empresa_id,
                obra_id=rdo.obra_id,
                workflow_id=etapa.workflow_id,
                etapa_id=etapa.id,
            )
            if manual_assignment_id and WorkflowService._usuario_elegivel_para_etapa(
                empresa_id=etapa.empresa_id,
                obra_id=rdo.obra_id,
                etapa=etapa,
                usuario_id=manual_assignment_id,
            ):
                return manual_assignment_id

        if etapa.usuario_aprovador_id:
            return etapa.usuario_aprovador_id

        papel = WorkflowService._papel_resolvido_etapa(etapa)

        if etapa.tipo_aprovador == 'RESPONSAVEL_OBRA' and rdo and rdo.obra and rdo.obra.usuario_responsavel_id:
            return rdo.obra.usuario_responsavel_id

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
        etapas_lista = list(etapas)
        grupos = {
            grupo.id: grupo
            for grupo in WorkflowGrupo.query.filter_by(
                workflow_id=workflow.id,
                ativo=True,
            ).order_by(WorkflowGrupo.ordem.asc(), WorkflowGrupo.id.asc()).all()
        }
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
            'grupos': [
                {
                    'id': grupo.id,
                    'nome': grupo.nome,
                    'ordem': grupo.ordem,
                    'regra_aprovacao': grupo.regra_aprovacao or 'TODOS',
                }
                for grupo in grupos.values()
            ],
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
                    'grupo_id': etapa.grupo_id,
                    'grupo_nome': etapa.grupo.nome if etapa.grupo else None,
                    'grupo_paralelo': etapa.grupo_paralelo,
                    'regra_aprovacao': (
                        etapa.grupo.regra_aprovacao
                        if etapa.grupo and etapa.grupo.regra_aprovacao
                        else 'TODOS'
                    ),
                    'obrigatorio': etapa.obrigatorio,
                    'obrigatoria': etapa.obrigatoria,
                    'assinatura_obrigatoria': etapa.assinatura_obrigatoria,
                    'sla_horas': etapa.sla_horas,
                }
                for etapa in etapas_lista
            ],
        }

    @staticmethod
    def _etapa_snapshot(etapa: WorkflowEtapa, aprovador_id: Optional[int]) -> Dict[str, Any]:
        regra_aprovacao = etapa.grupo.regra_aprovacao if etapa.grupo and etapa.grupo.regra_aprovacao else 'TODOS'
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
            'grupo_id': etapa.grupo_id,
            'grupo_nome': etapa.grupo.nome if etapa.grupo else None,
            'grupo_paralelo': etapa.grupo_paralelo,
            'regra_aprovacao': regra_aprovacao,
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

            WorkflowService._garantir_permissao_aprovacao(
                empresa_id=rdo.empresa_id,
                obra_id=rdo.obra_id,
                usuario_id=aprovador_id,
                papel_id=etapa.papel_id or (etapa.papel.id if etapa.papel else None),
            )

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
                grupo_id=etapa.grupo_id,
                grupo_paralelo=etapa.grupo_paralelo,
                regra_aprovacao=(
                    etapa.grupo.regra_aprovacao
                    if etapa.grupo and etapa.grupo.regra_aprovacao
                    else 'TODOS'
                ),
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
            WorkflowExecucaoEtapa.nivel == aprovacao.nivel,
        ).order_by(
            WorkflowExecucaoEtapa.nivel.asc(),
            *WorkflowService._order_by_nullable_asc(WorkflowExecucaoEtapa.ordem),
            WorkflowExecucaoEtapa.id.asc(),
        ).first()
        if etapa:
            return etapa

        etapa = WorkflowExecucaoEtapa.query.filter_by(
            execucao_id=execucao.id,
            usuario_resolvido_id=aprovacao.aprovador_id,
            ativo=True,
        ).filter(
            WorkflowExecucaoEtapa.status == 'PENDENTE',
        ).order_by(
            WorkflowExecucaoEtapa.nivel.asc(),
            *WorkflowService._order_by_nullable_asc(WorkflowExecucaoEtapa.ordem),
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
    def _etapa_execucao_regra_aprovacao(etapa: Optional[WorkflowExecucaoEtapa]) -> str:
        if not etapa:
            return 'TODOS'
        regra = etapa.regra_aprovacao or None
        if not regra and isinstance(etapa.etapa_snapshot, dict):
            regra = etapa.etapa_snapshot.get('regra_aprovacao') or etapa.etapa_snapshot.get('regra_etapa')
        regra_normalizada = str(regra or 'TODOS').strip().upper()
        if regra_normalizada in {'QUALQUER', 'PRIMEIRO', 'OU'}:
            return 'QUALQUER'
        return 'TODOS'

    @staticmethod
    def _query_etapas_mesmo_grupo(execucao_id: int, etapa: WorkflowExecucaoEtapa):
        query = WorkflowExecucaoEtapa.query.filter(
            WorkflowExecucaoEtapa.execucao_id == execucao_id,
            WorkflowExecucaoEtapa.ativo.is_(True),
        )
        if etapa.grupo_id:
            return query.filter(WorkflowExecucaoEtapa.grupo_id == etapa.grupo_id)
        if etapa.grupo_paralelo not in (None, '', 0, '0'):
            return query.filter(WorkflowExecucaoEtapa.grupo_paralelo == etapa.grupo_paralelo)
        return query.filter(WorkflowExecucaoEtapa.nivel == etapa.nivel)

    @staticmethod
    def _pular_pendentes_do_grupo_qualquer(
        rdo_id: int,
        etapa_aprovada: Optional[WorkflowExecucaoEtapa],
        aprovacao_executada_id: Optional[int],
    ) -> None:
        if not etapa_aprovada:
            return
        if WorkflowService._etapa_execucao_regra_aprovacao(etapa_aprovada) != 'QUALQUER':
            return

        actor_id = WorkflowService._ator_id()
        siblings = WorkflowService._query_etapas_mesmo_grupo(
            etapa_aprovada.execucao_id,
            etapa_aprovada,
        ).filter(
            WorkflowExecucaoEtapa.id != etapa_aprovada.id,
            WorkflowExecucaoEtapa.status == 'PENDENTE',
        ).all()

        for sibling in siblings:
            sibling.status = 'PULADO'
            sibling.comentario = 'Etapa dispensada: o grupo aceita aprovacao de qualquer responsavel.'
            sibling.modificado_por = actor_id
            sibling.modificado_em = utcnow_naive()
            db.session.add(sibling)

            aprovacao_query = RDOAprovacao.query.filter(
                RDOAprovacao.rdo_id == rdo_id,
                RDOAprovacao.status == 'PENDENTE',
                RDOAprovacao.ativo.is_(True),
            )
            if sibling.usuario_resolvido_id:
                aprovacao_query = aprovacao_query.filter(RDOAprovacao.aprovador_id == sibling.usuario_resolvido_id)
            if sibling.nivel is not None:
                aprovacao_query = aprovacao_query.filter(RDOAprovacao.nivel == sibling.nivel)

            aprovacoes_sibling = aprovacao_query.all()
            if not aprovacoes_sibling and sibling.usuario_resolvido_id:
                aprovacoes_sibling = RDOAprovacao.query.filter(
                    RDOAprovacao.rdo_id == rdo_id,
                    RDOAprovacao.aprovador_id == sibling.usuario_resolvido_id,
                    RDOAprovacao.status == 'PENDENTE',
                    RDOAprovacao.ativo.is_(True),
                ).all()

            for aprovacao in aprovacoes_sibling:
                if aprovacao_executada_id and aprovacao.id == aprovacao_executada_id:
                    continue
                aprovacao.ativo = False
                aprovacao.comentario = 'Dispensada pela regra do grupo: qualquer responsavel aprova.'
                aprovacao.modificado_por = actor_id
                aprovacao.modificado_em = utcnow_naive()
                db.session.add(aprovacao)

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
            *WorkflowService._order_by_nullable_asc(WorkflowExecucaoEtapa.ordem),
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
                    WorkflowService._pular_pendentes_do_grupo_qualquer(
                        aprovacao.rdo_id,
                        etapa_execucao,
                        aprovacao.id,
                    )

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

    @staticmethod
    def cancelar_execucao(
        rdo_id: int,
        motivo: Optional[str] = None,
        commit: bool = True,
    ) -> Tuple[bool, str]:
        try:
            execucao = WorkflowService.obter_execucao_ativa(rdo_id)
            if not execucao:
                return False, "Nenhuma execucao ativa encontrada para este workflow."
            if execucao.status not in {'PENDENTE', 'EM_ANDAMENTO', 'REABERTO'}:
                return False, "A execucao selecionada nao pode mais ser cancelada."

            rdo = db.session.get(RDO, rdo_id)
            if not rdo:
                return False, "RDO nao encontrado."

            WorkflowService._cancelar_fluxo(
                rdo_id=rdo_id,
                motivo=motivo or 'Fluxo cancelado manualmente.',
            )

            actor_id = WorkflowService._ator_id()
            rdo.status = 'CANCELADO'
            rdo.modificado_por = actor_id
            rdo.modificado_em = utcnow_naive()
            db.session.add(rdo)

            if commit:
                db.session.commit()
            else:
                db.session.flush()
            return True, "Workflow cancelado com sucesso."
        except Exception as exc:
            db.session.rollback()
            return False, str(exc)

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



