import json
from datetime import date

from app.routes.auth_common import *
from app.models.cliente import Cliente
from app.models.configuracao import ConfigDefinicao, EmpresaConfig, ObraConfig
from app.models.notificacao import TipoNotificacao
from app.models.obra import FrenteTrabalho, FrenteColaborador, ObraUsuario
from app.models.rdo import RDO, RDOAprovacao
from app.models.workflow import WorkflowDefinicao, WorkflowEtapa, WorkflowExecucao, WorkflowExecucaoEtapa, WorkflowGrupo
from app.services.config_service import ConfigService
from app.services.notificacao_service import NotificacaoService
from app.services.workflow_service import WorkflowResolucaoError, WorkflowService
from app.utils.export_service import make_csv_response, make_xlsx_response, make_pdf_response
from app.utils.datetime_utils import utcnow_naive
from app.models.usuario import Colaborador, Papel, UsuarioPapel
from sqlalchemy import func

WORKFLOW_OBRA_MVP_CODES = {"SIMPLES", "SEQUENCIAL", "PARALELO"}


def _is_workflow_obra_mvp(workflow):
    return bool(
        workflow
        and (
            (workflow.codigo or "").upper() in WORKFLOW_OBRA_MVP_CODES
            or (workflow.tipo_fluxo or "").upper() in WORKFLOW_OBRA_MVP_CODES
        )
    )

OBRA_EXPORT_COLUMNS = [
    ("id", "ID"),
    ("nome", "Projeto"),
    ("cnpj", "CNPJ"),
    ("cliente", "Cliente"),
    ("cidade", "Cidade"),
    ("estado", "Estado"),
    ("endereco", "Endereço"),
    ("tipo", "Tipo"),
    ("progresso", "Progresso"),
    ("status", "Status"),
]


def _get_centros_custo_options(empresa_id):
    if not empresa_id:
        return []

    rows = (
        db.session.query(FrenteTrabalho.centro_custo)
        .filter(FrenteTrabalho.empresa_id == empresa_id)
        .filter(FrenteTrabalho.centro_custo.isnot(None))
        .all()
    )
    values = sorted({(v or "").strip() for (v,) in rows if (v or "").strip()})
    return values


def _current_empresa_id(user=None):
    return session.get("empresa_id") or getattr(user, "empresa_id", None)


def _ensure_obra_workflow_config_definitions():
    definitions = {
        WorkflowService.WORKFLOW_DEFAULT_CONFIG_KEY: {
            "descricao": "Workflow padrao da obra",
            "tipo": "STRING",
            "valor_padrao": "",
        },
        WorkflowService.WORKFLOW_ASSIGNMENTS_CONFIG_KEY: {
            "descricao": "Responsaveis por etapa do workflow da obra",
            "tipo": "JSON",
            "valor_padrao": "{}",
        },
    }
    changed = False
    for chave, meta in definitions.items():
        definicao = ConfigDefinicao.query.filter_by(chave=chave).first()
        if definicao:
            continue
        definicao = ConfigDefinicao(
            chave=chave,
            descricao=meta["descricao"],
            tipo=meta["tipo"],
            valor_padrao=meta["valor_padrao"],
            is_system=True,
        )
        db.session.add(definicao)
        changed = True
    if changed:
        db.session.flush()


def _build_obra_workflow_setup_context(empresa_id, obra_id=None):
    base = {
        "enabled": bool(empresa_id),
        "available_workflows": [],
        "workflow_previews": {},
        "user_options": [],
        "selected_workflow_id": None,
        "selected_workflow_reference": "",
        "preview": {
            "workflow_id": None,
            "workflow_nome": "Sem workflow",
            "workflow_origem": "Sem workflow",
            "workflow_origem_tipo": "indefinido",
            "etapas": [],
            "valid": False,
            "errors": [],
        },
    }
    if not empresa_id:
        return base

    _ensure_obra_workflow_config_definitions()
    workflows = [
        workflow
        for workflow in WorkflowService.listar_workflows_disponiveis_obra(empresa_id, obra_id)
        if _is_workflow_obra_mvp(workflow)
    ]
    workflow_padrao_empresa = WorkflowService._resolver_workflow_empresa_padrao(empresa_id)
    workflow_padrao_id = (
        workflow_padrao_empresa.id
        if _is_workflow_obra_mvp(workflow_padrao_empresa)
        else (workflows[0].id if workflows else None)
    )
    papeis = (
        Papel.query
        .filter(
            Papel.ativo.is_(True),
            db.or_(Papel.empresa_id == empresa_id, Papel.empresa_id.is_(None)),
        )
        .order_by(Papel.empresa_id.is_(None), Papel.nome.asc())
        .all()
    )
    base["available_workflows"] = [
        {
            "id": workflow.id,
            "nome": workflow.nome,
            "codigo": workflow.codigo,
            "descricao": workflow.descricao,
            "tipo_fluxo": workflow.tipo_fluxo,
            "escopo": "obra" if workflow.obra_id else "empresa",
            "escopo_label": "Workflow da Obra" if workflow.obra_id else "Workflow da Empresa",
            "is_default": workflow.id == workflow_padrao_id,
        }
        for workflow in workflows
    ]
    base["default_workflow_id"] = workflow_padrao_id
    base["workflow_previews"] = {}
    for workflow in workflows:
        etapas_preview = WorkflowService.obter_etapas_ordenadas(workflow.id)
        base["workflow_previews"][str(workflow.id)] = {
            "workflow_id": workflow.id,
            "workflow_nome": workflow.nome,
            "workflow_codigo": workflow.codigo,
            "workflow_descricao": workflow.descricao,
            "tipo_fluxo": workflow.tipo_fluxo or "CONFIGURAVEL",
            "aprovacao_paralela": bool(workflow.aprovacao_paralela),
            "workflow_origem": "Padrao da Empresa" if workflow.id == workflow_padrao_id else "Workflow da Empresa",
            "workflow_origem_tipo": "empresa",
            "etapas": [
                {
                    "etapa_id": etapa.id,
                    "workflow_id": workflow.id,
                    "nivel": etapa.nivel,
                    "nome": etapa.nome,
                    "tipo_aprovador": "USUARIO" if etapa.tipo_aprovador == "USUARIO" else "PAPEL",
                    "papel_id": etapa.papel_id,
                    "papel_nome": etapa.papel.nome if etapa.papel else None,
                    "usuario_aprovador_id": etapa.usuario_aprovador_id,
                    "workflow_group": etapa.grupo.ordem if etapa.grupo else (etapa.grupo_paralelo or etapa.nivel),
                    "grupo_id": etapa.grupo_id,
                    "grupo_paralelo": etapa.grupo_paralelo,
                    "assinatura_obrigatoria": bool(etapa.assinatura_obrigatoria),
                    "regra_etapa": "PRIMEIRO" if etapa.grupo and etapa.grupo.regra_aprovacao == "QUALQUER" else "TODOS",
                    "regra_aprovacao": etapa.grupo.regra_aprovacao if etapa.grupo and etapa.grupo.regra_aprovacao else "TODOS",
                }
                for etapa in etapas_preview
            ],
            "valid": True,
            "errors": [],
        }
    base["role_options"] = [
        {"id": papel.id, "nome": papel.nome}
        for papel in papeis
    ]
    usuarios_empresa = sorted(
        Usuario.query
        .filter_by(empresa_id=empresa_id, ativo=True)
        .all(),
        key=lambda usuario: (usuario.nome or usuario.email or "").strip().lower(),
    )
    papeis_por_usuario = {}
    for usuario_papel in (
        UsuarioPapel.query
        .filter(
            UsuarioPapel.ativo.is_(True),
            db.or_(UsuarioPapel.empresa_id.is_(None), UsuarioPapel.empresa_id == empresa_id),
        )
        .all()
    ):
        papeis_por_usuario.setdefault(usuario_papel.usuario_id, set()).add(usuario_papel.papel_id)

    papeis_obra_por_usuario = {}
    if obra_id:
        for vinculo in (
            ObraUsuario.query
            .filter_by(empresa_id=empresa_id, obra_id=obra_id, ativo=True)
            .all()
        ):
            if vinculo.papel_id:
                papeis_obra_por_usuario.setdefault(vinculo.usuario_id, set()).add(vinculo.papel_id)

    base["user_options"] = [
        {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "papel_ids": sorted(papeis_por_usuario.get(usuario.id, set())),
            "obra_papel_ids": sorted(papeis_obra_por_usuario.get(usuario.id, set())),
            "vinculado_obra": usuario.id in papeis_obra_por_usuario,
        }
        for usuario in usuarios_empresa
    ]

    if not obra_id:
        base["selected_workflow_id"] = workflow_padrao_id
        workflow_padrao = next((workflow for workflow in workflows if workflow.id == workflow_padrao_id), None)
        if workflow_padrao:
            etapas = WorkflowService.obter_etapas_ordenadas(workflow_padrao.id)
            base["preview"] = {
                "workflow_id": workflow_padrao.id,
                "workflow_nome": workflow_padrao.nome,
                "workflow_codigo": workflow_padrao.codigo,
                "workflow_descricao": workflow_padrao.descricao,
                "tipo_fluxo": workflow_padrao.tipo_fluxo or "CONFIGURAVEL",
                "aprovacao_paralela": bool(workflow_padrao.aprovacao_paralela),
                "workflow_origem": "Padrao da Empresa",
                "workflow_origem_tipo": "empresa",
                "etapas": [
                    {
                        "etapa_id": etapa.id,
                        "workflow_id": workflow_padrao.id,
                        "nivel": etapa.nivel,
                        "nome": etapa.nome,
                        "tipo_aprovador": "USUARIO" if etapa.tipo_aprovador == "USUARIO" else "PAPEL",
                        "papel_id": etapa.papel_id,
                        "papel_nome": etapa.papel.nome if etapa.papel else None,
                        "usuario_aprovador_id": etapa.usuario_aprovador_id,
                        "workflow_group": etapa.grupo.ordem if etapa.grupo else (etapa.grupo_paralelo or etapa.nivel),
                        "grupo_id": etapa.grupo_id,
                        "grupo_paralelo": etapa.grupo_paralelo,
                        "assinatura_obrigatoria": bool(etapa.assinatura_obrigatoria),
                        "regra_etapa": "PRIMEIRO" if etapa.grupo and etapa.grupo.regra_aprovacao == "QUALQUER" else "TODOS",
                        "regra_aprovacao": etapa.grupo.regra_aprovacao if etapa.grupo and etapa.grupo.regra_aprovacao else "TODOS",
                    }
                    for etapa in etapas
                ],
                "valid": True,
                "errors": [],
            }
        return base

    config_workflow = ObraConfig.query.filter_by(
        empresa_id=empresa_id,
        obra_id=obra_id,
        chave=WorkflowService.WORKFLOW_DEFAULT_CONFIG_KEY,
    ).first()
    selected_reference = (config_workflow.valor or "").strip() if config_workflow and config_workflow.valor else ""
    workflow_aplicado = WorkflowService.resolver_workflow(empresa_id, obra_id)
    selected_workflow_id = workflow_aplicado.id if workflow_aplicado else None
    if selected_reference:
        workflow_override = WorkflowService._resolver_workflow_por_referencia(
            empresa_id=empresa_id,
            referencia=selected_reference,
            obra_id=obra_id,
            incluir_workflows_obra=True,
        )
        if workflow_override:
            selected_workflow_id = workflow_override.id

    base["selected_workflow_id"] = selected_workflow_id
    base["selected_workflow_reference"] = selected_reference
    if selected_workflow_id:
        base["preview"] = WorkflowService.construir_preview_workflow_obra(
            empresa_id=empresa_id,
            obra_id=obra_id,
            workflow_id=selected_workflow_id,
        )
        if selected_reference:
            base["preview"]["workflow_origem"] = "Configurado na Obra"
            base["preview"]["workflow_origem_tipo"] = "obra"

    return base


def _set_obra_config_value(empresa_id, obra_id, chave, valor):
    row = ObraConfig.query.filter_by(
        empresa_id=empresa_id,
        obra_id=obra_id,
        chave=chave,
    ).first()

    if valor in (None, "", {}, []):
        if row:
            db.session.delete(row)
        return

    serialized = json.dumps(valor, ensure_ascii=True) if isinstance(valor, (dict, list)) else str(valor)
    if row:
        row.valor = serialized
        return

    db.session.add(
        ObraConfig(
            empresa_id=empresa_id,
            obra_id=obra_id,
            chave=chave,
            valor=serialized,
        )
    )


def _resolver_papel_empresa_por_nome(empresa_id, nome):
    nome_normalizado = (nome or "").strip().upper()
    if not nome_normalizado:
        return None
    return (
        Papel.query
        .filter(
            func.upper(func.trim(Papel.nome)) == nome_normalizado,
            Papel.ativo.is_(True),
            db.or_(Papel.empresa_id == empresa_id, Papel.empresa_id.is_(None)),
        )
        .order_by(Papel.empresa_id.is_(None), Papel.id.asc())
        .first()
    )


def _ensure_usuario_gestor_obra(empresa_id, obra, usuario_id, criado_por=None):
    if not empresa_id or not obra or not usuario_id:
        return

    papel_gestor = _resolver_papel_empresa_por_nome(empresa_id, ROLE_GESTOR)
    if not papel_gestor:
        return

    usuario_papel = UsuarioPapel.query.filter_by(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        papel_id=papel_gestor.id,
    ).first()
    if not usuario_papel:
        usuario_papel = UsuarioPapel(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            papel_id=papel_gestor.id,
            ativo=True,
        )
        db.session.add(usuario_papel)
    else:
        usuario_papel.ativo = True
        db.session.add(usuario_papel)

    vinculo = ObraUsuario.query.filter_by(
        empresa_id=empresa_id,
        obra_id=obra.id,
        usuario_id=usuario_id,
    ).first()
    if not vinculo:
        vinculo = ObraUsuario(
            empresa_id=empresa_id,
            obra_id=obra.id,
            usuario_id=usuario_id,
            papel_id=papel_gestor.id,
            ativo=True,
            criado_por=criado_por,
        )
        set_audit_on_create(vinculo, user_id=criado_por)
        db.session.add(vinculo)
    else:
        vinculo.ativo = True
        if vinculo.papel_id in (None, papel_gestor.id):
            vinculo.papel_id = papel_gestor.id
        set_audit_on_update(vinculo, user_id=criado_por)
        db.session.add(vinculo)


def _workflow_tem_historico_execucao(workflow_id):
    if not workflow_id:
        return False
    return (
        db.session.query(WorkflowExecucaoEtapa.id)
        .join(WorkflowEtapa, WorkflowEtapa.id == WorkflowExecucaoEtapa.etapa_definicao_id)
        .filter(WorkflowEtapa.workflow_id == workflow_id)
        .first()
        is not None
    )


def _arquivar_workflow_obra(workflow, actor_id):
    if not workflow:
        return

    nome_suffix = f" [Hist {workflow.id}]"
    codigo_suffix = f"_H{workflow.id}"
    workflow.ativo = False
    workflow.nome = f"{(workflow.nome or 'Workflow')[:max(1, 150 - len(nome_suffix))]}{nome_suffix}"
    workflow.codigo = f"{(workflow.codigo or f'OBRA_{workflow.obra_id}_{workflow.id}')[:max(1, 50 - len(codigo_suffix))]}{codigo_suffix}"
    workflow.modificado_por = actor_id
    db.session.add(workflow)
    db.session.flush()


def _normalizar_regra_aprovacao_obra(valor):
    regra = str(valor or "TODOS").strip().upper()
    return "QUALQUER" if regra in {"QUALQUER", "PRIMEIRO", "OU"} else "TODOS"


def _get_workflow_obra_no_escopo(empresa_id, obra_id, workflow_id):
    return WorkflowService.obter_workflow_no_escopo_obra(empresa_id, obra_id, workflow_id)


def _upsert_obra_workflow_customizado(empresa_id, obra, source_workflow, workflow_config_data, actor_id):
    custom_stages = workflow_config_data.get("custom_stages") if isinstance(workflow_config_data.get("custom_stages"), list) else []
    if not custom_stages:
        return None

    expected_codigo = f"OBRA_{obra.id}_{source_workflow.id}" if source_workflow else f"OBRA_{obra.id}"
    expected_nome = source_workflow.nome if source_workflow else f"Workflow {obra.nome}"
    expected_descricao = source_workflow.descricao if source_workflow else f"Workflow customizado da obra {obra.nome}"
    expected_tipo_fluxo = source_workflow.tipo_fluxo if source_workflow else 'CONFIGURAVEL'

    workflows_obra = (
        WorkflowDefinicao.query
        .filter_by(empresa_id=empresa_id, obra_id=obra.id)
        .order_by(WorkflowDefinicao.ativo.desc(), WorkflowDefinicao.id.asc())
        .all()
    )

    workflow = next((item for item in workflows_obra if item.ativo), None)
    if not workflow and source_workflow:
        workflow = next(
            (
                item for item in workflows_obra
                if item.nome == expected_nome or item.codigo == expected_codigo
            ),
            None,
        )
    if not workflow and workflows_obra:
        workflow = workflows_obra[0]

    if workflow and _workflow_tem_historico_execucao(workflow.id):
        _arquivar_workflow_obra(workflow, actor_id)
        workflow = None

    if not workflow:
        workflow = WorkflowDefinicao(
            empresa_id=empresa_id,
            obra_id=obra.id,
            codigo=expected_codigo,
            nome=expected_nome,
            descricao=expected_descricao,
            tipo_fluxo=expected_tipo_fluxo,
            aprovacao_paralela=bool(workflow_config_data.get("aprovacao_paralela")),
            rejeicao_cancela_fluxo=(source_workflow.rejeicao_cancela_fluxo if source_workflow else True),
            cliente_obrigatorio=(source_workflow.cliente_obrigatorio if source_workflow else False),
            assinatura_obrigatoria=(source_workflow.assinatura_obrigatoria if source_workflow else False),
            permite_reprovar=(source_workflow.permite_reprovar if source_workflow else True),
            comentario_reprovacao_obrigatorio=(source_workflow.comentario_reprovacao_obrigatorio if source_workflow else True),
            sla_horas=(source_workflow.sla_horas if source_workflow else None),
            sla_global_horas=(source_workflow.sla_global_horas if source_workflow else None),
            permite_reabertura=(source_workflow.permite_reabertura if source_workflow else True),
            permite_cancelamento=(source_workflow.permite_cancelamento if source_workflow else True),
            ativo=True,
            criado_por=actor_id,
            modificado_por=actor_id,
        )
        db.session.add(workflow)
        db.session.flush()
    else:
        workflow.ativo = True
        workflow.codigo = expected_codigo
        workflow.nome = expected_nome
        workflow.descricao = expected_descricao
        workflow.tipo_fluxo = expected_tipo_fluxo
        workflow.aprovacao_paralela = bool(workflow_config_data.get("aprovacao_paralela"))
        if source_workflow:
            workflow.rejeicao_cancela_fluxo = source_workflow.rejeicao_cancela_fluxo
            workflow.cliente_obrigatorio = source_workflow.cliente_obrigatorio
            workflow.assinatura_obrigatoria = source_workflow.assinatura_obrigatoria
            workflow.permite_reprovar = source_workflow.permite_reprovar
            workflow.comentario_reprovacao_obrigatorio = source_workflow.comentario_reprovacao_obrigatorio
            workflow.sla_horas = source_workflow.sla_horas
            workflow.sla_global_horas = source_workflow.sla_global_horas
            workflow.permite_reabertura = source_workflow.permite_reabertura
            workflow.permite_cancelamento = source_workflow.permite_cancelamento
        workflow.modificado_por = actor_id
        db.session.add(workflow)

    for etapa in WorkflowEtapa.query.filter_by(workflow_id=workflow.id).all():
        db.session.delete(etapa)
    db.session.flush()

    for grupo in WorkflowGrupo.query.filter_by(workflow_id=workflow.id).all():
        db.session.delete(grupo)
    db.session.flush()

    is_simple = (workflow.tipo_fluxo or "").upper() == "SIMPLES"
    grupos_por_chave = {}
    for index, stage in enumerate(custom_stages, start=1):
        if is_simple:
            group_key = "1"
        else:
            group_key = str(
                stage.get("workflow_group")
                or stage.get("grupo_visual")
                or stage.get("grupo_paralelo")
                or index
            )
        if group_key in grupos_por_chave:
            continue
        grupo = WorkflowGrupo(
            empresa_id=empresa_id,
            workflow_id=workflow.id,
            nome="Etapa 1" if is_simple else f"Grupo {len(grupos_por_chave) + 1}",
            ordem=len(grupos_por_chave) + 1,
            regra_aprovacao=_normalizar_regra_aprovacao_obra(
                stage.get("regra_aprovacao") or stage.get("regra_etapa")
            ),
            ativo=True,
            criado_por=actor_id,
            modificado_por=actor_id,
        )
        db.session.add(grupo)
        grupos_por_chave[group_key] = grupo
    db.session.flush()

    for index, stage in enumerate(custom_stages, start=1):
        nome_etapa = (stage.get("nome") or "").strip()
        if not nome_etapa:
            continue
        tipo_aprovador = (stage.get("tipo_aprovador") or "PAPEL").strip().upper()
        papel_id = stage.get("papel_id")
        usuario_aprovador_id = stage.get("usuario_aprovador_id")
        if is_simple:
            group_key = "1"
        else:
            group_key = str(
                stage.get("workflow_group")
                or stage.get("grupo_visual")
                or stage.get("grupo_paralelo")
                or index
            )
        grupo = grupos_por_chave.get(group_key)
        grupo_paralelo = grupo.ordem if workflow.aprovacao_paralela and grupo else None
        db.session.add(
            WorkflowEtapa(
                empresa_id=empresa_id,
                workflow_id=workflow.id,
                nivel=index,
                ordem=index,
                nome=nome_etapa,
                tipo_aprovador=tipo_aprovador if tipo_aprovador in {'USUARIO', 'PAPEL', 'CLIENTE', 'RESPONSAVEL_OBRA'} else 'PAPEL',
                papel_id=int(papel_id) if papel_id not in (None, "") else None,
                usuario_aprovador_id=int(usuario_aprovador_id) if usuario_aprovador_id not in (None, "") else None,
                grupo_id=grupo.id if grupo else None,
                grupo_paralelo=grupo_paralelo,
                obrigatorio=True,
                obrigatoria=True,
                assinatura_obrigatoria=bool(stage.get("assinatura_obrigatoria")),
                ativo=True,
                criado_por=actor_id,
                modificado_por=actor_id,
            )
        )

    return workflow


def _format_datetime_br(value):
    if not value:
        return "-"
    return value.strftime("%d/%m/%Y %H:%M")


def _humanize_duration(start, end=None, prefix=None):
    if not start:
        return "-"

    end_value = end or utcnow_naive()
    delta = end_value - start
    total_seconds = max(int(delta.total_seconds()), 0)
    minutes = max(total_seconds // 60, 1)

    if minutes >= 60 * 24:
        days = minutes // (60 * 24)
        label = f"{days} dia" if days == 1 else f"{days} dias"
    elif minutes >= 60:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        label = f"{hours}h"
        if remaining_minutes:
            label += f" {remaining_minutes}min"
    else:
        label = f"{minutes} min"

    return f"{prefix}{label}" if prefix else label


def _normalize_workflow_status(status):
    normalized = (status or "").upper()
    return {
        "PENDENTE": {
            "label": "Pendente",
            "badge_class": "border-amber-200 bg-amber-50 text-amber-800",
            "dot_class": "bg-amber-500",
            "icon": "fa-hourglass-half",
        },
        "EM_ANDAMENTO": {
            "label": "Em andamento",
            "badge_class": "border-blue-200 bg-blue-50 text-blue-700",
            "dot_class": "bg-blue-500",
            "icon": "fa-spinner",
        },
        "APROVADO": {
            "label": "Concluído",
            "badge_class": "border-emerald-200 bg-emerald-50 text-emerald-700",
            "dot_class": "bg-emerald-500",
            "icon": "fa-check-circle",
        },
        "REJEITADO": {
            "label": "Rejeitado",
            "badge_class": "border-rose-200 bg-rose-50 text-rose-700",
            "dot_class": "bg-rose-500",
            "icon": "fa-circle-xmark",
        },
        "CANCELADO": {
            "label": "Cancelado",
            "badge_class": "border-slate-200 bg-slate-100 text-slate-700",
            "dot_class": "bg-slate-500",
            "icon": "fa-ban",
        },
        "REABERTO": {
            "label": "Em andamento",
            "badge_class": "border-blue-200 bg-blue-50 text-blue-700",
            "dot_class": "bg-blue-500",
            "icon": "fa-rotate-left",
        },
        "ERRO": {
            "label": "Erro",
            "badge_class": "border-red-200 bg-red-50 text-red-700",
            "dot_class": "bg-red-500",
            "icon": "fa-triangle-exclamation",
        },
    }.get(normalized, {
        "label": normalized.title() if normalized else "Indefinido",
        "badge_class": "border-slate-200 bg-slate-100 text-slate-700",
        "dot_class": "bg-slate-500",
        "icon": "fa-circle-question",
    })


def _extract_workflow_error(payload):
    if not isinstance(payload, dict):
        return None

    nested = payload.get("erro") if isinstance(payload.get("erro"), dict) else payload.get("error")
    if isinstance(nested, dict):
        message = (
            nested.get("message")
            or nested.get("mensagem")
            or nested.get("descricao")
            or nested.get("detail")
        )
        code = nested.get("code") or nested.get("codigo")
        if message or code:
            return {"message": message or "Erro ao executar workflow.", "code": code}

    message = (
        payload.get("error")
        or payload.get("erro")
        or payload.get("error_message")
        or payload.get("mensagem_erro")
        or payload.get("mensagem")
        or payload.get("detail")
    )
    code = payload.get("error_code") or payload.get("codigo_erro")
    if not message and not code:
        return None
    return {"message": message or "Erro ao executar workflow.", "code": code}


def _workflow_step_visual_status(step_status):
    return {
        "NAO_INICIADA": {
            "label": "Não iniciada",
            "badge_class": "border-slate-200 bg-slate-100 text-slate-600",
            "icon": "fa-lock",
            "card_class": "border-slate-200 bg-slate-50/70",
        },
        "AGUARDANDO": {
            "label": "Aguardando",
            "badge_class": "border-amber-200 bg-amber-50 text-amber-800",
            "icon": "fa-hourglass-half",
            "card_class": "border-amber-200 bg-amber-50/40",
        },
        "EM_EXECUCAO": {
            "label": "Em execução",
            "badge_class": "border-blue-200 bg-blue-50 text-blue-700",
            "icon": "fa-spinner",
            "card_class": "border-blue-200 bg-blue-50/40",
        },
        "APROVADO": {
            "label": "Aprovada",
            "badge_class": "border-emerald-200 bg-emerald-50 text-emerald-700",
            "icon": "fa-check-circle",
            "card_class": "border-emerald-200 bg-white",
        },
        "REJEITADO": {
            "label": "Rejeitada",
            "badge_class": "border-rose-200 bg-rose-50 text-rose-700",
            "icon": "fa-circle-xmark",
            "card_class": "border-rose-200 bg-rose-50/40",
        },
        "CANCELADA": {
            "label": "Cancelada",
            "badge_class": "border-slate-200 bg-slate-100 text-slate-700",
            "icon": "fa-ban",
            "card_class": "border-slate-200 bg-slate-50/80",
        },
        "ERRO": {
            "label": "Erro",
            "badge_class": "border-red-200 bg-red-50 text-red-700",
            "icon": "fa-triangle-exclamation",
            "card_class": "border-red-200 bg-red-50/50",
        },
        "IGNORADA": {
            "label": "Ignorada",
            "badge_class": "border-zinc-200 bg-zinc-100 text-zinc-700",
            "icon": "fa-forward",
            "card_class": "border-zinc-200 bg-zinc-50/70",
        },
    }[step_status]


def _build_workflow_execution_history(empresa_id, obra_id):
    if not empresa_id or not obra_id:
        return []

    execucoes = (
        WorkflowExecucao.query
        .filter_by(empresa_id=empresa_id, obra_id=obra_id)
        .order_by(
            WorkflowExecucao.iniciado_em.desc(),
            WorkflowExecucao.id.desc(),
        )
        .all()
    )

    history = []
    now = utcnow_naive()
    for execucao in execucoes:
        etapas = (
            WorkflowExecucaoEtapa.query
            .filter_by(execucao_id=execucao.id, ativo=True)
            .order_by(
                WorkflowExecucaoEtapa.nivel.asc(),
                *WorkflowService._order_by_nullable_asc(WorkflowExecucaoEtapa.ordem),
                WorkflowExecucaoEtapa.id.asc(),
            )
            .all()
        )
        workflow_snapshot = execucao.workflow_snapshot or {}
        workflow_error = _extract_workflow_error(workflow_snapshot)
        step_errors = []
        for etapa in etapas:
            error = _extract_workflow_error(etapa.etapa_snapshot or {})
            if error:
                step_errors.append((etapa.id, error))

        status_code = "ERRO" if workflow_error or step_errors else (execucao.status or "PENDENTE").upper()
        status_meta = _normalize_workflow_status(status_code)
        execution_number = f"{(execucao.iniciado_em or now).year}-{execucao.id:06d}"

        requester = getattr(execucao.rdo, "usuario", None) if execucao.rdo else None
        requester_name = (
            getattr(requester, "nome", None)
            or getattr(execucao.criador, "nome", None)
            or "Não identificado"
        )

        current_level = execucao.etapa_atual_nivel
        stage_start_by_level = {}
        completed_by_level = {}
        levels = sorted({etapa.nivel for etapa in etapas})
        previous_finished_at = execucao.iniciado_em
        for level in levels:
            stage_start_by_level[level] = previous_finished_at or execucao.iniciado_em
            finished_times = [
                etapa.aprovado_em
                for etapa in etapas
                if etapa.nivel == level and etapa.aprovado_em
            ]
            if finished_times:
                completed_by_level[level] = max(finished_times)
                previous_finished_at = completed_by_level[level]

        current_stage = None
        serialized_steps = []
        rejected_step = None
        for etapa in etapas:
            snapshot = etapa.etapa_snapshot or {}
            error = _extract_workflow_error(snapshot)
            stage_start = stage_start_by_level.get(etapa.nivel) or execucao.iniciado_em
            role_name = getattr(etapa.papel, "nome", None) or snapshot.get("papel_nome")
            user_name = getattr(etapa.usuario_resolvido, "nome", None) or snapshot.get("usuario_nome")

            if error:
                visual_status = "ERRO"
                status_message = "Erro ao executar"
                detail_message = error.get("message")
            elif etapa.status == "APROVADO":
                visual_status = "APROVADO"
                status_message = "Aprovado por"
                detail_message = user_name or "Usuário não identificado"
            elif etapa.status == "REJEITADO":
                visual_status = "REJEITADO"
                status_message = "Rejeitado por"
                detail_message = user_name or "Usuário não identificado"
                rejected_step = rejected_step or etapa
            elif etapa.status == "CANCELADO":
                visual_status = "CANCELADA"
                status_message = "Cancelada"
                detail_message = etapa.comentario or "Fluxo interrompido."
            elif etapa.status == "PULADO":
                visual_status = "IGNORADA"
                status_message = "Ignorada"
                detail_message = etapa.comentario or "Etapa não necessária nesta execução."
            elif current_level and etapa.nivel == current_level and status_code in {"PENDENTE", "EM_ANDAMENTO", "REABERTO", "ERRO"}:
                visual_status = "EM_EXECUCAO" if status_code != "PENDENTE" else "AGUARDANDO"
                status_message = "Aguardando aprovação"
                detail_message = _humanize_duration(stage_start, now, prefix="Há ")
                current_stage = current_stage or etapa
            else:
                visual_status = "NAO_INICIADA"
                status_message = "Aguardando etapa anterior"
                detail_message = ""

            serialized_steps.append({
                "id": etapa.id,
                "nivel": etapa.nivel,
                "ordem": etapa.ordem,
                "nome": etapa.nome,
                "tipo_aprovador": etapa.tipo_aprovador,
                "papel_nome": role_name,
                "usuario_nome": user_name,
                "status": visual_status,
                "status_raw": etapa.status,
                "status_message": status_message,
                "detail_message": detail_message,
                "badge_class": _workflow_step_visual_status(visual_status)["badge_class"],
                "card_class": _workflow_step_visual_status(visual_status)["card_class"],
                "icon": _workflow_step_visual_status(visual_status)["icon"],
                "status_label": _workflow_step_visual_status(visual_status)["label"],
                "aprovado_em_label": _format_datetime_br(etapa.aprovado_em) if etapa.aprovado_em else None,
                "duracao_label": _humanize_duration(stage_start, etapa.aprovado_em or now) if stage_start else "-",
                "comentario": etapa.comentario,
                "erro": error,
            })

        total_steps = len(serialized_steps)
        approved_steps = sum(1 for step in serialized_steps if step["status"] == "APROVADO")
        waiting_steps = sum(1 for step in serialized_steps if step["status"] in {"AGUARDANDO", "EM_EXECUCAO"})
        failed_steps = sum(1 for step in serialized_steps if step["status"] in {"REJEITADO", "CANCELADA", "ERRO"})
        idle_steps = max(total_steps - approved_steps - waiting_steps - failed_steps, 0)
        progress_percent = int(round((approved_steps / total_steps) * 100)) if total_steps else 0
        rdo = execucao.rdo
        rdo_number_value = getattr(rdo, "numero_sequencial", None) or getattr(rdo, "id", None) or execucao.rdo_id
        rdo_label = f"RDO #{rdo_number_value}" if rdo_number_value else "RDO nao identificado"
        rdo_date = getattr(rdo, "data_rdo", None)
        rdo_date_label = rdo_date.strftime("%d/%m/%Y") if rdo_date else "-"
        rdo_status = (getattr(rdo, "status", None) or "-").replace("_", " ").title()
        finished_at_label = _format_datetime_br(execucao.finalizado_em)
        current_stage_label = (
            current_stage.nome if current_stage
            else (
                "Concluida" if status_code == "APROVADO"
                else "Rejeitada" if status_code == "REJEITADO"
                else "Cancelada" if status_code == "CANCELADO"
                else "Sem etapa atual"
            )
        )
        origem_label = (execucao.origem or "AUTO").replace("_", " ").title()

        if status_code == "APROVADO":
            summary_title = "Workflow concluído com sucesso"
            summary_lines = [
                {"label": "Tempo total", "value": _humanize_duration(execucao.iniciado_em, execucao.finalizado_em or now)},
                {"label": "Resumo", "value": "Todas as etapas executadas."},
            ]
        elif status_code in {"PENDENTE", "EM_ANDAMENTO", "REABERTO"}:
            summary_title = "Workflow em andamento"
            summary_lines = [
                {"label": "Etapa atual", "value": current_stage.nome if current_stage else "Aguardando definição"},
            ]
        elif status_code == "REJEITADO":
            summary_title = "Workflow rejeitado"
            summary_lines = [
                {"label": "Etapa", "value": rejected_step.nome if rejected_step else "Não identificada"},
                {"label": "Motivo", "value": rejected_step.comentario if rejected_step and rejected_step.comentario else "Sem motivo informado."},
            ]
        elif status_code == "CANCELADO":
            summary_title = "Workflow cancelado"
            summary_lines = [
                {"label": "Tempo total", "value": _humanize_duration(execucao.iniciado_em, execucao.finalizado_em or now)},
                {"label": "Resumo", "value": "A execução foi interrompida antes da conclusão."},
            ]
        else:
            summary_title = "Workflow com erro"
            summary_lines = [
                {"label": "Falha", "value": (workflow_error or (step_errors[0][1] if step_errors else {})).get("message", "Erro não detalhado.")},
                {"label": "Código", "value": (workflow_error or (step_errors[0][1] if step_errors else {})).get("code") or "Não informado"},
            ]

        history.append({
            "id": execucao.id,
            "execution_number": execution_number,
            "status": status_code,
            "status_label": status_meta["label"],
            "status_badge_class": status_meta["badge_class"],
            "status_dot_class": status_meta["dot_class"],
            "status_icon": status_meta["icon"],
            "started_at_label": _format_datetime_br(execucao.iniciado_em),
            "finished_at_label": finished_at_label,
            "duration_label": _humanize_duration(
                execucao.iniciado_em,
                execucao.finalizado_em or now,
                prefix="Em execução há " if status_code in {"PENDENTE", "EM_ANDAMENTO", "REABERTO"} else None,
            ),
            "duration_plain_label": _humanize_duration(execucao.iniciado_em, execucao.finalizado_em or now),
            "requester_name": requester_name,
            "workflow_name": workflow_snapshot.get("nome") or getattr(execucao.workflow, "nome", None) or "Workflow não identificado",
            "rdo_id": execucao.rdo_id,
            "rdo_label": rdo_label,
            "rdo_date_label": rdo_date_label,
            "rdo_status_label": rdo_status,
            "origin_label": origem_label,
            "current_stage_label": current_stage_label,
            "active_label": "Ativa" if execucao.ativo else "Encerrada",
            "progress_percent": progress_percent,
            "steps_total": total_steps,
            "steps_approved": approved_steps,
            "steps_waiting": waiting_steps,
            "steps_failed": failed_steps,
            "steps_idle": idle_steps,
            "started_at_iso": execucao.iniciado_em.isoformat() if execucao.iniciado_em else None,
            "finished_at_iso": execucao.finalizado_em.isoformat() if execucao.finalizado_em else None,
            "created_at_label": _format_datetime_br(execucao.criado_em),
            "updated_at_label": _format_datetime_br(execucao.modificado_em),
            "summary_title": summary_title,
            "summary_lines": summary_lines,
            "solicitante": requester_name,
            "topo": {
                "status": status_meta["label"],
                "iniciado_em": _format_datetime_br(execucao.iniciado_em),
                "tempo": _humanize_duration(execucao.iniciado_em, execucao.finalizado_em or now),
                "solicitante": requester_name,
            },
            "error": workflow_error,
            "steps": serialized_steps,
        })

    return history


def _build_obra_governanca_context(empresa_id, obra_id=None):
    workflow_setup = _build_obra_workflow_setup_context(empresa_id, obra_id)
    workflow_preview = workflow_setup.get("preview") or {}
    workflow_preview_etapas = workflow_preview.get("etapas") or []
    workflow_tipo_fluxo = (workflow_preview.get("tipo_fluxo") or "CONFIGURAVEL").upper()
    workflow_regra = (
        next((etapa.get("regra_etapa") for etapa in workflow_preview_etapas if etapa.get("regra_etapa")), None)
        or "TODOS"
    )
    workflow_assinatura_obrigatoria = any(bool(etapa.get("assinatura_obrigatoria")) for etapa in workflow_preview_etapas)
    base = {
        "definicoes_total": 0,
        "overrides_total": 0,
        "configs_resolvidas": [],
        "overrides": [],
        "workflow_proprio": None,
        "workflow_aplicado": None,
        "workflow_origem": "Sem workflow",
        "workflow_origem_tipo": "indefinido",
        "workflow_etapas": [],
        "workflow_execucoes_historico": [],
        "workflow_setup": workflow_setup,
        "workflow_tem_config_propria": False,
        "workflow_summary": {
            "workflow_atual": workflow_preview.get("workflow_nome") or "Sem workflow",
            "origem": workflow_preview.get("workflow_origem") or "Sistema",
            "origem_tipo": workflow_preview.get("workflow_origem_tipo") or "sistema",
            "assinatura_obrigatoria": workflow_assinatura_obrigatoria,
            "regra_aprovacao": "Primeiro a responder" if str(workflow_regra).upper().startswith("PRIMEIRO") else "Todos devem aprovar",
            "tipo_fluxo": workflow_tipo_fluxo.title() if workflow_tipo_fluxo in {"SIMPLES", "SEQUENCIAL", "PARALELO"} else workflow_tipo_fluxo.title(),
        },
    }
    if not empresa_id:
        return base

    definicoes = ConfigDefinicao.query.order_by(ConfigDefinicao.chave.asc()).all()
    base["definicoes_total"] = len(definicoes)

    if not obra_id:
        return base

    mapa_resolvido = ConfigService.obter_mapa_config(empresa_id=empresa_id, obra_id=obra_id)
    empresa_cfg_map = {
        cfg.chave: cfg.valor
        for cfg in EmpresaConfig.query.filter_by(empresa_id=empresa_id).all()
    }
    obra_cfg_rows = ObraConfig.query.filter_by(empresa_id=empresa_id, obra_id=obra_id).all()
    obra_cfg_map = {cfg.chave: cfg for cfg in obra_cfg_rows}

    configs_resolvidas = []
    for definicao in definicoes:
        valor_resolvido = mapa_resolvido.get(definicao.chave)
        if valor_resolvido in (None, "", []):
            continue

        origem = "Sistema"
        if definicao.chave in empresa_cfg_map:
            origem = "Empresa"
        if definicao.chave in obra_cfg_map:
            origem = "Obra"

        configs_resolvidas.append({
            "chave": definicao.chave,
            "descricao": definicao.descricao,
            "tipo": definicao.tipo,
            "valor": valor_resolvido,
            "origem": origem,
            "has_override": definicao.chave in obra_cfg_map,
        })

    workflow_proprio = (
        WorkflowDefinicao.query
        .filter_by(empresa_id=empresa_id, obra_id=obra_id, ativo=True)
        .order_by(WorkflowDefinicao.nome.asc())
        .first()
    )
    workflow_aplicado = WorkflowService.resolver_workflow(empresa_id, obra_id)
    workflow_etapas = WorkflowService.obter_etapas_ordenadas(workflow_aplicado.id) if workflow_aplicado else []
    workflow_tipo_fluxo = (workflow_preview.get("tipo_fluxo") or getattr(workflow_aplicado, "tipo_fluxo", None) or "CONFIGURAVEL").upper()
    workflow_tem_config_propria = bool(
        workflow_proprio
        or WorkflowService.WORKFLOW_DEFAULT_CONFIG_KEY in obra_cfg_map
        or WorkflowService.WORKFLOW_ASSIGNMENTS_CONFIG_KEY in obra_cfg_map
    )

    base.update({
        "overrides_total": len(obra_cfg_rows),
        "configs_resolvidas": configs_resolvidas,
        "overrides": [
            {
                "chave": cfg.chave,
                "descricao": cfg.definicao.descricao if cfg.definicao else None,
                "tipo": cfg.definicao.tipo if cfg.definicao else "STRING",
                "valor": cfg.valor,
                "origem": "Obra",
                "has_override": True,
            }
            for cfg in obra_cfg_rows
        ],
        "workflow_proprio": workflow_proprio,
        "workflow_aplicado": workflow_aplicado,
        "workflow_origem": workflow_preview.get("workflow_origem") if workflow_preview else ("Workflow Proprio da Obra" if workflow_proprio else ("Herdado da Empresa" if workflow_aplicado else "Sem workflow")),
        "workflow_origem_tipo": workflow_preview.get("workflow_origem_tipo") if workflow_preview else ("obra" if workflow_proprio else ("empresa" if workflow_aplicado else "indefinido")),
        "workflow_etapas": workflow_etapas,
        "workflow_setup": workflow_setup,
        "workflow_tem_config_propria": workflow_tem_config_propria,
        "workflow_summary": {
            "workflow_atual": workflow_preview.get("workflow_nome") or (workflow_aplicado.nome if workflow_aplicado else "Sem workflow"),
            "origem": workflow_preview.get("workflow_origem") or ("Obra" if workflow_proprio else ("Empresa" if workflow_aplicado else "Sistema")),
            "origem_tipo": workflow_preview.get("workflow_origem_tipo") or ("obra" if workflow_proprio else ("empresa" if workflow_aplicado else "sistema")),
            "assinatura_obrigatoria": workflow_assinatura_obrigatoria,
            "regra_aprovacao": "Primeiro a responder" if str(workflow_regra).upper().startswith("PRIMEIRO") else "Todos devem aprovar",
            "tipo_fluxo": workflow_tipo_fluxo.title() if workflow_tipo_fluxo in {"SIMPLES", "SEQUENCIAL", "PARALELO"} else workflow_tipo_fluxo.title(),
        },
        "workflow_execucoes_historico": _build_workflow_execution_history(empresa_id, obra_id),
    })
    return base


def _render_workflow_historico_execucoes_html(empresa_id, obra_id, view_mode=False):
    obra_governanca = _build_obra_governanca_context(empresa_id, obra_id)
    return render_template(
        "cadastros/obras/_workflow_historico_execucoes.html",
        obra_governanca=obra_governanca,
        view_mode=view_mode,
    )


def _get_obras_permitidas_ids(user, empresa_id):
    if not user or not empresa_id:
        return []

    if getattr(user, "is_admin", False):
        return [
            obra_id
            for (obra_id,) in (
                db.session.query(Obra.id)
                .filter(Obra.empresa_id == empresa_id)
                .all()
            )
        ]

    return [
        obra_id
        for (obra_id,) in (
            db.session.query(ObraUsuario.obra_id)
            .filter(
                ObraUsuario.usuario_id == user.id,
                ObraUsuario.empresa_id == empresa_id,
                ObraUsuario.ativo.is_(True),
            )
            .all()
        )
    ]


def _apply_obras_usuario_scope(query, user, empresa_id):
    if not user or not empresa_id:
        return query.filter(False)

    if getattr(user, "is_admin", False):
        return query.filter(Obra.empresa_id == empresa_id)

    return (
        query
        .join(
            ObraUsuario,
            db.and_(
                ObraUsuario.obra_id == Obra.id,
                ObraUsuario.empresa_id == Obra.empresa_id,
            ),
        )
        .filter(
            Obra.empresa_id == empresa_id,
            ObraUsuario.usuario_id == user.id,
            ObraUsuario.ativo.is_(True),
        )
        .distinct()
    )


def _get_admin_users_empresa(empresa_id):
    if not empresa_id:
        return []

    admin_names = {ROLE_ADMIN, "ADMINISTRADOR"}
    admins = (
        Usuario.query
        .join(UsuarioPapel, UsuarioPapel.usuario_id == Usuario.id)
        .join(Papel, Papel.id == UsuarioPapel.papel_id)
        .filter(
            Usuario.empresa_id == empresa_id,
            db.or_(UsuarioPapel.empresa_id.is_(None), UsuarioPapel.empresa_id == empresa_id),
            Usuario.ativo.is_(True),
            UsuarioPapel.ativo.is_(True),
            Papel.ativo.is_(True),
            func.upper(func.trim(Papel.nome)).in_(admin_names),
            db.or_(Papel.empresa_id.is_(None), Papel.empresa_id == empresa_id),
        )
        .distinct()
        .all()
    )
    admin_ids = {admin.id for admin in admins}

    for usuario in Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).all():
        if usuario.id not in admin_ids and getattr(usuario, "is_admin", False):
            admins.append(usuario)
            admin_ids.add(usuario.id)

    return admins


def _ensure_obra_usuario_access(obra, usuario_id, criado_por=None):
    if not obra or not usuario_id:
        return

    obra_usuario = ObraUsuario.query.filter_by(
        empresa_id=obra.empresa_id,
        obra_id=obra.id,
        usuario_id=usuario_id,
    ).first()
    if obra_usuario:
        obra_usuario.ativo = True
        set_audit_on_update(obra_usuario, user_id=criado_por)
        return

    novo_vinculo = ObraUsuario(
        empresa_id=obra.empresa_id,
        obra_id=obra.id,
        usuario_id=usuario_id,
        ativo=True,
        criado_por=criado_por,
    )
    set_audit_on_create(novo_vinculo, user_id=criado_por)
    db.session.add(novo_vinculo)


def _sync_admin_obras_empresa(empresa_id, criado_por=None):
    if not empresa_id:
        return 0

    admins = _get_admin_users_empresa(empresa_id)
    obras = Obra.query.filter_by(empresa_id=empresa_id).all()
    if not admins or not obras:
        return 0

    existentes = {
        (obra_id, usuario_id): ativo
        for obra_id, usuario_id, ativo in (
            db.session.query(ObraUsuario.obra_id, ObraUsuario.usuario_id, ObraUsuario.ativo)
            .filter(ObraUsuario.empresa_id == empresa_id)
            .all()
        )
    }

    alterados = 0
    for admin in admins:
        for obra in obras:
            chave = (obra.id, admin.id)
            if chave not in existentes or existentes[chave] is not True:
                _ensure_obra_usuario_access(obra, admin.id, criado_por=criado_por or admin.id)
                existentes[chave] = True
                alterados += 1

    return alterados


def _parse_export_columns(default_columns):
    requested = request.args.get("columns", "")
    if not requested:
        return [key for key, _ in default_columns]

    requested_keys = [key.strip() for key in requested.split(",") if key.strip()]
    selected = [key for key, _ in default_columns if key in requested_keys]
    return selected or [key for key, _ in default_columns]


def _parse_export_ids():
    raw_ids = request.args.get("ids", "")
    if not raw_ids:
        return []

    ids = []
    for part in raw_ids.split(","):
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def _calculate_progress(obra):
    total = 0
    count = 0
    for frente in obra.frentes_trabalho or []:
        plan = frente.qtd_planejada or 0
        real = frente.qtd_realizada or 0
        if plan > 0:
            total += min(100, (real / plan) * 100)
            count += 1
    return int(total / count) if count else 0


def _build_obra_export_cell(obra, key):
    if key == "id":
        return obra.id
    if key == "nome":
        return obra.nome
    if key == "cnpj":
        return obra.cnpj or ""
    if key == "cliente":
        return obra.contratante or ""
    if key == "cidade":
        return obra.cidade or ""
    if key == "estado":
        return obra.estado or ""
    if key == "endereco":
        return obra.endereco or ""
    if key == "tipo":
        return obra.tipo_obra.nome if getattr(obra, "tipo_obra", None) else ""
    if key == "progresso":
        return f"{_calculate_progress(obra)}%"
    if key == "status":
        return "Ativa" if obra.status == 1 else "Inativa"
    return ""


@auth_bp.get("/lista-obras")
@auth_bp.get("/obras")
@login_required
def lista_obras():
    user = Usuario.query.get(session.get("user_id"))
    empresa_id = _current_empresa_id(user)
    if user and getattr(user, "is_admin", False):
        try:
            if _sync_admin_obras_empresa(empresa_id, criado_por=user.id):
                db.session.commit()
        except Exception:
            db.session.rollback()

    query = Obra.query.order_by(Obra.id.asc())
    query = _apply_obras_usuario_scope(query, user, empresa_id)

    resultados = query.all()

    user_ids = set()
    for obra_obj in resultados:
        if obra_obj.criado_por:
            user_ids.add(obra_obj.criado_por)
        if obra_obj.modificado_por:
            user_ids.add(obra_obj.modificado_por)

    user_name_by_id = {}
    if user_ids:
        for u in Usuario.query.filter(Usuario.id.in_(list(user_ids))).all():
            user_name_by_id[u.id] = u.nome

    obras_formatadas = []
    for obra_obj in resultados:
        obra_dict = {
            'id': obra_obj.id,
            'nome': obra_obj.nome,
            'cnpj': obra_obj.cnpj,
            'cliente': obra_obj.contratante,
            'cidade': obra_obj.cidade,
            'estado': obra_obj.estado,
            'endereco': obra_obj.endereco,
            'numero': obra_obj.numero,
            'complemento': obra_obj.complemento,
            'bairro': obra_obj.bairro,
            'cep': obra_obj.cep,
            'tipo': obra_obj.tipo_obra.nome if obra_obj.tipo_obra else None,
            'status': obra_obj.status,
            'frentes_trabalho': obra_obj.frentes_trabalho,
            'criado_em': obra_obj.criado_em,
            'modificado_em': obra_obj.modificado_em,
            'criado_por': obra_obj.criado_por,
            'modificado_por': obra_obj.modificado_por,
            'criado_por_nome': user_name_by_id.get(obra_obj.criado_por) if obra_obj.criado_por else None,
            'modificado_por_nome': user_name_by_id.get(obra_obj.modificado_por) if obra_obj.modificado_por else None,
        }
        obras_formatadas.append(obra_dict)

    return render_template("cadastros/obras/list_obras.html", opcoes=obras_formatadas, categoria="obra")


@auth_bp.get('/lista-obras/export/<string:export_format>')
@auth_bp.get('/obras/export/<string:export_format>')
@login_required
def export_lista_obras(export_format):
    user = Usuario.query.get(session.get("user_id"))
    empresa_id = _current_empresa_id(user)
    if user and getattr(user, "is_admin", False):
        try:
            if _sync_admin_obras_empresa(empresa_id, criado_por=user.id):
                db.session.commit()
        except Exception:
            db.session.rollback()

    ids = _parse_export_ids()
    requested_columns = _parse_export_columns(OBRA_EXPORT_COLUMNS)

    query = Obra.query.filter_by(empresa_id=empresa_id).order_by(Obra.nome.asc())
    query = _apply_obras_usuario_scope(query, user, empresa_id)

    if ids:
        query = query.filter(Obra.id.in_(ids))

    obras = query.all()
    headers = [label for key, label in OBRA_EXPORT_COLUMNS if key in requested_columns]
    rows = [[_build_obra_export_cell(obra, key) for key in requested_columns] for obra in obras]

    if export_format == 'csv':
        return make_csv_response(headers, rows, prefix='obras')
    if export_format == 'xlsx':
        return make_xlsx_response(headers, rows, prefix='obras')
    if export_format == 'pdf':
        return make_pdf_response(
            'exports/export_generic_table.html',
            {'title': 'Cadastro de Obras', 'headers': headers, 'rows': rows},
            prefix='obras',
        )

    abort(404)


@auth_bp.get("/criar-obra")
@auth_bp.get("/obras/nova")
@auth_bp.get("/obras/novo")
@login_required
@permission_required('obra.manage')
def criar_obra():
    usuarios = Usuario.query.filter_by(status=1).all()
    clientes = Cliente.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).order_by(Cliente.razao_social.asc()).all()
    tipos_obra = AuxTipoObra.query.filter_by(ativo=True).order_by(AuxTipoObra.nome.asc()).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    centros_custo = _get_centros_custo_options(session.get('empresa_id'))
    return render_template(
        "cadastros/obras/form_obra.html",
        item=None,
        usuarios=usuarios,
        clientes=clientes,
        tipos_obra=tipos_obra,
        mao_de_obra_options=mao_de_obra_options,
        equipe_obra=[],
        centros_custo=centros_custo,
        obra_governanca=_build_obra_governanca_context(session.get('empresa_id')),
    )

@auth_bp.post("/mudar-status-obras/<int:obraid>")
@auth_bp.post("/obras/<int:obraid>/toggle-status")
@login_required
@permission_required('obra.manage')
def toggle_user_obras(obraid):
    # Security scope check
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and obraid not in scope_ids:
        return {"message": "Forbidden"}, 403

    empresa_id = session.get('empresa_id')
    obra = Obra.query.filter_by(id=obraid, empresa_id=empresa_id).first_or_404()
    obra.status = not obra.status
    set_audit_on_update(obra)
    try:
        db.session.commit()
        return {"message": "Status atualizado com sucesso"}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"Erro ao atualizar: {str(e)}"}, 500

@auth_bp.route('/gerar-obra', methods=['POST'])
@auth_bp.post('/obras/salvar')
@login_required
@permission_required('obra.manage')
def gerar_obra():
    def _parse_date(value):
        value = (value or "").strip()
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    def _parse_time(value):
        value = (value or "").strip()
        if not value:
            return None
        return datetime.strptime(value, "%H:%M").time()

    def _parse_bool(value, default=False):
        if value is None:
            return default
        value = str(value).strip().lower()
        if value in ("1", "true", "t", "yes", "y", "on"):
            return True
        if value in ("0", "false", "f", "no", "n", "off"):
            return False
        return default

    def _validation_error(message):
        flash(message, "danger")
        return redirect(url_for("auth.lista_obras"))

    obra_id = request.form.get("id")
    if obra_id:
        # Security scope
        scope_ids = get_user_scope_ids()
        if scope_ids is not None and int(obra_id) not in scope_ids:
             flash("Sem permissão para editar esta obra", "danger")
             return redirect(url_for('auth.lista_obras'))

    cnpj_obra = request.form.get('cnpj_obra')
    cliente_id = request.form.get('cliente_id')

    if not cliente_id:
        flash("Erro: selecione um cliente válido para esta obra.", "danger")
        return redirect(url_for('auth.lista_obras'))

    cliente = Cliente.query.filter_by(id=cliente_id, empresa_id=session.get('empresa_id')).first()
    if not cliente:
        flash("Erro: cliente inválido.", "danger")
        return redirect(url_for('auth.lista_obras'))

    obra_existente = Obra.query.filter_by(cnpj_obra=cnpj_obra).first() if cnpj_obra else None
    if obra_existente:
        if not obra_id or str(obra_existente.id) != str(obra_id):
            flash(f"Erro: O CNPJ {cnpj_obra} já está cadastrado.", "danger")
            return redirect(url_for('auth.lista_obras'))

    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Erro: o nome da obra é obrigatório.", "danger")
        return redirect(url_for("auth.lista_obras"))

    criado_por = session.get('user_id')
    audit_user_id = get_current_user_id()

    # Campos do schema (com fallback para nomes legados)
    data_inicio_str = request.form.get("data_inicio") or request.form.get("inicio")
    data_fim_planejada_str = request.form.get("data_fim_planejada")
    data_fim_str = request.form.get("data_fim") or request.form.get("termino")

    hora_entrada_padrao_str = request.form.get("hora_entrada_padrao") or request.form.get("horario_entrada")
    intervalo_entrada_padrao_str = request.form.get("intervalo_entrada_padrao")
    intervalo_saida_padrao_str = request.form.get("intervalo_saida_padrao")
    hora_saida_padrao_str = request.form.get("hora_saida_padrao") or request.form.get("horario_saida")

    cep = request.form.get('cep')
    ibge_municipio = request.form.get('ibge_municipio')
    logradouro = request.form.get("logradouro") or request.form.get("endereco")
    numero = request.form.get('numero')
    complemento = request.form.get('complemento')
    bairro = request.form.get('bairro')
    cidade = request.form.get('cidade')
    estado = request.form.get('estado')

    tipo_obra_id_raw = (request.form.get("tipo_obra_id") or "").strip() or None
    usuario_responsavel_id_raw = (request.form.get("usuario_responsavel_id") or request.form.get("id_responsavel") or "").strip() or None
    ativo = _parse_bool(request.form.get("ativo"), default=_parse_bool(request.form.get("status"), default=True))
    frentes_payload = request.form.get('frentes_json')
    equipe_payload = request.form.get('equipe_obra_json')
    workflow_selected_raw = (request.form.get('workflow_selecionado_id') or "").strip()
    workflow_config_payload = request.form.get('workflow_config_json')

    is_new_obra = not obra_id

    try:
        data_inicio = _parse_date(data_inicio_str)
        data_fim_planejada = _parse_date(data_fim_planejada_str)
        data_fim = _parse_date(data_fim_str)
        frentes_data = json.loads(frentes_payload) if frentes_payload else {}
        workflow_config_data = json.loads(workflow_config_payload) if workflow_config_payload else {}
        if not isinstance(workflow_config_data, dict):
            workflow_config_data = {}

        if data_inicio and data_fim_planejada and data_fim_planejada < data_inicio:
            return _validation_error("Erro: a data de fim planejada não pode anteceder a data de início da obra.")

        if data_inicio and data_fim and data_fim < data_inicio:
            return _validation_error("Erro: a data de fim real não pode anteceder a data de início da obra.")

        limite_obra = min([d for d in (data_fim_planejada, data_fim) if d], default=None)
        frentes_para_validar = list(frentes_data.get("novas", [])) + list(frentes_data.get("editadas", []))
        for indice, frente_data in enumerate(frentes_para_validar, start=1):
            frente_nome = (frente_data.get("nome_frente") or f"Frente {indice}").strip()
            frente_inicio = _parse_date(frente_data.get("data_inicio"))
            frente_fim_planejada = _parse_date(frente_data.get("data_planejada") or frente_data.get("data_fim_planejada"))
            frente_fim = _parse_date(frente_data.get("data_fim"))

            if data_inicio and frente_inicio and frente_inicio < data_inicio:
                return _validation_error(f"Erro: a data de início da frente '{frente_nome}' não pode anteceder a data de início da obra.")

            if frente_inicio and frente_fim_planejada and frente_fim_planejada < frente_inicio:
                return _validation_error(f"Erro: a data de fim planejada da frente '{frente_nome}' não pode anteceder sua data de início.")

            if frente_inicio and frente_fim and frente_fim < frente_inicio:
                return _validation_error(f"Erro: a data de fim real da frente '{frente_nome}' não pode anteceder sua data de início.")

            if limite_obra and frente_fim_planejada and frente_fim_planejada > limite_obra:
                return _validation_error(f"Erro: a data de fim planejada da frente '{frente_nome}' não pode ultrapassar o prazo da obra.")

            if limite_obra and frente_fim and frente_fim > limite_obra:
                return _validation_error(f"Erro: a data de fim real da frente '{frente_nome}' não pode ultrapassar o prazo da obra.")

        cep_limpo = ''.join(ch for ch in (cep or "") if ch.isdigit())
        if not obra_id and cep_limpo and (len(cep_limpo) != 8 or not cidade or not estado or not ibge_municipio):
            return _validation_error("Erro: informe um CEP válido para carregar Cidade, Estado e IBGE.")

        hora_entrada_padrao = _parse_time(hora_entrada_padrao_str)
        intervalo_entrada_padrao = _parse_time(intervalo_entrada_padrao_str)
        intervalo_saida_padrao = _parse_time(intervalo_saida_padrao_str)
        hora_saida_padrao = _parse_time(hora_saida_padrao_str)

        tipo_obra_id = int(tipo_obra_id_raw) if tipo_obra_id_raw else None
        usuario_responsavel_id = int(usuario_responsavel_id_raw) if usuario_responsavel_id_raw else None

        if usuario_responsavel_id:
            usuario_resp = Usuario.query.filter_by(id=usuario_responsavel_id, status=1).first()
            if not usuario_resp:
                flash("Erro: o responsável da obra deve ser um usuário ativo.", "danger")
                return redirect(url_for("auth.lista_obras"))

        if tipo_obra_id:
            tipo_obra = AuxTipoObra.query.filter_by(id=tipo_obra_id, ativo=True).first()
            if not tipo_obra:
                flash("Erro: tipo de obra inválido.", "danger")
                return redirect(url_for("auth.lista_obras"))

        if obra_id:
            empresa_id = session.get('empresa_id')
            obra = Obra.query.filter_by(id=obra_id, empresa_id=empresa_id).first()
            obra.nome = nome
            obra.cnpj_obra = cnpj_obra
            obra.cliente_id = cliente.id
            obra.tipo_obra_id = tipo_obra_id
            obra.usuario_responsavel_id = usuario_responsavel_id
            obra.data_inicio = data_inicio
            obra.data_fim_planejada = data_fim_planejada
            obra.data_fim = data_fim
            obra.hora_entrada_padrao = hora_entrada_padrao
            obra.intervalo_entrada_padrao = intervalo_entrada_padrao
            obra.intervalo_saida_padrao = intervalo_saida_padrao
            obra.hora_saida_padrao = hora_saida_padrao
            obra.cep = cep
            obra.logradouro = logradouro
            obra.numero = numero
            obra.complemento = complemento
            obra.bairro = bairro
            obra.cidade = cidade
            obra.estado = estado
            obra.ativo = ativo
            set_audit_on_update(obra, user_id=audit_user_id)
            flash("Obra atualizada com sucesso!", "success")
        else:
            obra = Obra(
                empresa_id=session.get('empresa_id'),
                nome=nome,
                cliente_id=cliente.id,
                cnpj_obra=cnpj_obra,
                criado_por=criado_por if criado_por else None,
                tipo_obra_id=tipo_obra_id,
                usuario_responsavel_id=usuario_responsavel_id,
                data_inicio=data_inicio,
                data_fim_planejada=data_fim_planejada,
                data_fim=data_fim,
                hora_entrada_padrao=hora_entrada_padrao,
                intervalo_entrada_padrao=intervalo_entrada_padrao,
                intervalo_saida_padrao=intervalo_saida_padrao,
                hora_saida_padrao=hora_saida_padrao,
                cep=cep,
                logradouro=logradouro,
                numero=numero,
                complemento=complemento,
                bairro=bairro,
                cidade=cidade,
                estado=estado,
                ativo=ativo
            )
            set_audit_on_create(obra, user_id=audit_user_id)
            db.session.add(obra)
            db.session.flush()
            flash("Obra cadastrada com sucesso!", "success")

            usuarios_com_acesso = {criado_por} if criado_por else set()
            usuarios_com_acesso.update(admin.id for admin in _get_admin_users_empresa(obra.empresa_id))
            for usuario_id in usuarios_com_acesso:
                _ensure_obra_usuario_access(obra, usuario_id, criado_por=criado_por)

        if frentes_payload:
            data = frentes_data
            for f_id in data.get('removidas', []):
                if not f_id:
                    continue
                frente = FrenteTrabalho.query.filter_by(frente_trabalho_id=f_id, obra_id=obra.id, empresa_id=obra.empresa_id).first()
                if frente:
                    set_audit_on_inactivate(frente, user_id=audit_user_id)

            for f_nova in data.get('novas', []):
                nova_frente = FrenteTrabalho(
                    empresa_id=session.get('empresa_id'),
                    obra_id=obra.id,
                    nome_frente=(f_nova.get('nome_frente') or '').strip() or None,
                    centro_custo=f_nova.get('centro_custo'),
                    data_inicio=datetime.strptime(f_nova.get('data_inicio'), '%Y-%m-%d').date() if f_nova.get('data_inicio') else None,
                    data_planejada=datetime.strptime(f_nova.get('data_planejada'), '%Y-%m-%d').date() if f_nova.get('data_planejada') else None,
                    data_fim=datetime.strptime(f_nova.get('data_fim'), '%Y-%m-%d').date() if f_nova.get('data_fim') else None,
                    ativo=_parse_bool(f_nova.get('ativo'), default=True),
                )
                set_audit_on_create(nova_frente, user_id=audit_user_id)
                db.session.add(nova_frente)

            for f_edit in data.get('editadas', []):
                frente_id = f_edit.get('frente_trabalho_id') or f_edit.get('id_frente_trabalho')
                frente_existente = FrenteTrabalho.query.get(frente_id)
                if frente_existente and frente_existente.obra_id == obra.id:
                    frente_existente.nome_frente = (f_edit.get('nome_frente') or '').strip() or None
                    frente_existente.centro_custo = f_edit.get('centro_custo')
                    frente_existente.data_inicio = datetime.strptime(f_edit.get('data_inicio'), '%Y-%m-%d').date() if f_edit.get('data_inicio') else None
                    frente_existente.data_planejada = datetime.strptime(f_edit.get('data_planejada'), '%Y-%m-%d').date() if f_edit.get('data_planejada') else None
                    frente_existente.data_fim = datetime.strptime(f_edit.get('data_fim'), '%Y-%m-%d').date() if f_edit.get('data_fim') else None
                    frente_existente.ativo = _parse_bool(f_edit.get('ativo'), default=True)
                    set_audit_on_update(frente_existente, user_id=audit_user_id)

        if usuario_responsavel_id:
            _ensure_usuario_gestor_obra(obra.empresa_id, obra, usuario_responsavel_id, criado_por=audit_user_id)

        # Em obra nova, o workflow do formulario e gravado apos o flush da obra.
        _ensure_obra_workflow_config_definitions()
        workflow_assignments = workflow_config_data.get("assignments") if isinstance(workflow_config_data.get("assignments"), dict) else {}
        workflow_customizado = bool(workflow_config_data.get("customizado"))
        workflow_custom_stages = (
            workflow_config_data.get("custom_stages")
            if workflow_customizado and isinstance(workflow_config_data.get("custom_stages"), list)
            else []
        )
        workflow_draft_error = None
        if workflow_selected_raw:
            try:
                workflow_selected_id = int(workflow_selected_raw)
            except ValueError:
                raise WorkflowResolucaoError("Workflow selecionado invÃ¡lido para a obra.")

            workflow_source = _get_workflow_obra_no_escopo(
                obra.empresa_id,
                obra.id,
                workflow_selected_id,
            )
            if not workflow_source:
                raise WorkflowResolucaoError("Workflow selecionado Ã© invÃ¡lido para esta empresa.")
            if not _is_workflow_obra_mvp(workflow_source):
                raise WorkflowResolucaoError("Nesta tela, selecione apenas os workflows Simples, Sequencial ou Paralelo.")
            custom_workflow = None
            if workflow_customizado:
                custom_workflow = _upsert_obra_workflow_customizado(
                    empresa_id=obra.empresa_id,
                    obra=obra,
                    source_workflow=workflow_source,
                    workflow_config_data={**workflow_config_data, "custom_stages": workflow_custom_stages},
                    actor_id=audit_user_id,
                )
            workflow_alvo = custom_workflow or workflow_source
            if custom_workflow and workflow_custom_stages:
                workflow_assignments = {}
                etapas_customizadas = WorkflowService.obter_etapas_ordenadas(custom_workflow.id)
                for etapa_customizada, stage_payload in zip(etapas_customizadas, workflow_custom_stages):
                    responsavel_usuario_id = stage_payload.get("responsavel_usuario_id")
                    if responsavel_usuario_id in (None, ""):
                        continue
                    try:
                        workflow_assignments[str(etapa_customizada.id)] = int(responsavel_usuario_id)
                    except (TypeError, ValueError):
                        continue
            validado = None
            try:
                validado = WorkflowService.validar_configuracao_workflow_obra(
                    empresa_id=obra.empresa_id,
                    obra_id=obra.id,
                    workflow_id=workflow_alvo.id,
                    assignments=workflow_assignments,
                    auto_grant_signature=True,
                )
            except WorkflowResolucaoError as exc:
                if not is_new_obra:
                    raise
                workflow_draft_error = str(exc)
            _set_obra_config_value(
                empresa_id=obra.empresa_id,
                obra_id=obra.id,
                chave=WorkflowService.WORKFLOW_DEFAULT_CONFIG_KEY,
                valor=(f"id:{workflow_source.id}" if workflow_source and not custom_workflow else None),
            )
            _set_obra_config_value(
                empresa_id=obra.empresa_id,
                obra_id=obra.id,
                chave=WorkflowService.WORKFLOW_ASSIGNMENTS_CONFIG_KEY,
                valor={
                    "workflow_id": validado["workflow"].id,
                    "assignments": validado["assignments"],
                } if validado else None,
            )
            if workflow_draft_error:
                flash(
                    "Workflow salvo como rascunho. Para ativar ou testar, vincule os usuarios/papeis pendentes: "
                    f"{workflow_draft_error}",
                    "warning",
                )
        else:
            _set_obra_config_value(
                empresa_id=obra.empresa_id,
                obra_id=obra.id,
                chave=WorkflowService.WORKFLOW_DEFAULT_CONFIG_KEY,
                valor=None,
            )
            _set_obra_config_value(
                empresa_id=obra.empresa_id,
                obra_id=obra.id,
                chave=WorkflowService.WORKFLOW_ASSIGNMENTS_CONFIG_KEY,
                valor=None,
            )

        db.session.commit()
        return redirect(url_for('auth.lista_obras'))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar a solicitação: {str(e)}", "danger")
        return redirect(url_for('auth.lista_obras'))

@auth_bp.get("/editar-obra/<int:id>")
@auth_bp.get("/obras/<int:id>/editar")
@login_required
@permission_required('obra.manage')
def editar_obra(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        abort(403)

    empresa_id = session.get('empresa_id')
    obra = hydrate_audit_metadata(Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    frentes = (
        FrenteTrabalho.query
        .filter_by(obra_id=id, empresa_id=empresa_id)
        # MySQL não suporta "NULLS LAST" no ORDER BY. Usamos expressão booleana para empurrar NULLs pro fim.
        .order_by(FrenteTrabalho.data_inicio.is_(None), FrenteTrabalho.data_inicio.asc(), FrenteTrabalho.id.asc())
        .all()
    )
    usuarios = Usuario.query.filter_by(status=1).all()
    clientes = Cliente.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).order_by(Cliente.razao_social.asc()).all()
    tipos_obra = AuxTipoObra.query.filter_by(ativo=True).order_by(AuxTipoObra.nome.asc()).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    equipe_obra = _get_equipe_obra_payload(id)
    centros_custo = _get_centros_custo_options(session.get('empresa_id'))
    return render_template(
        "cadastros/obras/form_obra.html",
        item=obra,
        frentes=frentes,
        usuarios=usuarios,
        clientes=clientes,
        tipos_obra=tipos_obra,
        mao_de_obra_options=mao_de_obra_options,
        equipe_obra=equipe_obra,
        centros_custo=centros_custo,
        obra_governanca=_build_obra_governanca_context(empresa_id, id),
    )

@auth_bp.get("/visualizar-obra/<int:id>")
@auth_bp.get("/obras/<int:id>")
@login_required
def visualizar_obra(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        flash("Acesso restrito.", "danger")
        return redirect(url_for('auth.lista_obras'))

    empresa_id = session.get('empresa_id')
    item = hydrate_audit_metadata(Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404())
    usuarios = Usuario.query.filter_by(status=1).all()
    clientes = Cliente.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).order_by(Cliente.razao_social.asc()).all()
    tipos_obra = AuxTipoObra.query.filter_by(ativo=True).order_by(AuxTipoObra.nome.asc()).all()
    frentes = (
        FrenteTrabalho.query
        .filter_by(obra_id=id, empresa_id=empresa_id)
        .order_by(FrenteTrabalho.data_inicio.is_(None), FrenteTrabalho.data_inicio.asc(), FrenteTrabalho.id.asc())
        .all()
    )
    usuario = (
        Usuario.query.filter_by(status=1)
        .outerjoin(Colaborador, Usuario.colaborador_id == Colaborador.id)
        .order_by(func.coalesce(Colaborador.nome, Usuario.email).asc())
        .all()
    )
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    equipe_obra = _get_equipe_obra_payload(id)
    centros_custo = _get_centros_custo_options(session.get('empresa_id'))

    return render_template(
        "cadastros/obras/form_obra.html",
        item=item,
        view_mode=True,
        categoria="obra",
        frentes=frentes,
        usuario=usuario,
        usuarios=usuarios,
        clientes=clientes,
        tipos_obra=tipos_obra,
        mao_de_obra_options=mao_de_obra_options,
        equipe_obra=equipe_obra,
        centros_custo=centros_custo,
        obra_governanca=_build_obra_governanca_context(empresa_id, id),
    )


@auth_bp.get("/obras/<int:id>/workflow-preview")
@login_required
@permission_required('obra.manage')
def preview_workflow_obra(id):
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return jsonify({"ok": False, "error": "Acesso negado para esta obra."}), 403

    empresa_id = session.get('empresa_id')
    obra = Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    workflow_id_raw = request.args.get("workflow_id")
    workflow_id = None
    if workflow_id_raw not in (None, ""):
        try:
            workflow_id = int(workflow_id_raw)
        except ValueError:
            return jsonify({"ok": False, "error": "Workflow invalido."}), 400
        workflow = _get_workflow_obra_no_escopo(empresa_id, obra.id, workflow_id)
        if not workflow:
            return jsonify({"ok": False, "error": "Workflow invalido para esta obra."}), 404
        if not _is_workflow_obra_mvp(workflow):
            return jsonify({"ok": False, "error": "Use apenas os workflows Simples, Sequencial ou Paralelo nesta tela."}), 400

    preview = WorkflowService.construir_preview_workflow_obra(
        empresa_id=empresa_id,
        obra_id=obra.id,
        workflow_id=workflow_id,
    )
    return jsonify({"ok": True, "preview": preview})


@auth_bp.post("/obras/<int:id>/workflow-restaurar-padrao")
@login_required
@permission_required('obra.manage')
def restaurar_workflow_padrao_obra(id):
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return jsonify({"ok": False, "error": "Acesso negado para esta obra."}), 403

    empresa_id = session.get('empresa_id')
    obra = Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()

    ObraConfig.query.filter(
        ObraConfig.empresa_id == empresa_id,
        ObraConfig.obra_id == obra.id,
        ObraConfig.chave.in_([
            WorkflowService.WORKFLOW_DEFAULT_CONFIG_KEY,
            WorkflowService.WORKFLOW_ASSIGNMENTS_CONFIG_KEY,
        ]),
    ).delete(synchronize_session=False)

    workflows_proprios = WorkflowDefinicao.query.filter_by(
        empresa_id=empresa_id,
        obra_id=obra.id,
        ativo=True,
    ).all()
    for workflow in workflows_proprios:
        workflow.ativo = False
        workflow.modificado_por = session.get("user_id")
        db.session.add(workflow)

    db.session.commit()
    preview = WorkflowService.construir_preview_workflow_obra(
        empresa_id=empresa_id,
        obra_id=obra.id,
    )
    return jsonify({"ok": True, "preview": preview})


@auth_bp.post("/obras/<int:id>/workflow-testar")
@login_required
@permission_required('obra.manage')
def testar_workflow_obra(id):
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return jsonify({"ok": False, "error": "Acesso negado para esta obra."}), 403

    empresa_id = session.get('empresa_id')
    actor_id = session.get('user_id')
    obra = Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()

    workflow_id = None
    payload = request.get_json(silent=True) or {}
    workflow_id_raw = str(payload.get('workflow_id') or request.form.get('workflow_id') or '').strip()
    if workflow_id_raw:
        try:
            workflow_id = int(workflow_id_raw)
        except ValueError:
            return jsonify({"ok": False, "error": "Workflow invalido."}), 400

    workflow = (
        _get_workflow_obra_no_escopo(empresa_id, obra.id, workflow_id)
        if workflow_id
        else WorkflowService.resolver_workflow(empresa_id, obra.id)
    )
    if not workflow:
        return jsonify({"ok": False, "error": "Nenhum workflow ativo encontrado para esta obra."}), 400
    if not _is_workflow_obra_mvp(workflow):
        return jsonify({"ok": False, "error": "Use apenas os workflows Simples, Sequencial ou Paralelo nesta tela."}), 400

    preview = WorkflowService.construir_preview_workflow_obra(
        empresa_id=empresa_id,
        obra_id=obra.id,
        workflow_id=workflow.id,
    )
    validation_errors = [str(error) for error in (preview.get('errors') or []) if error]
    if not preview.get('etapas'):
        validation_errors.append("O workflow selecionado nao possui etapas ativas para testar.")
    for etapa in preview.get('etapas') or []:
        etapa_nome = etapa.get('nome') or f"Etapa {etapa.get('nivel') or etapa.get('etapa_id') or ''}".strip()
        if etapa.get('fallback_empresa'):
            if etapa.get('tipo_aprovador') == 'PAPEL' and etapa.get('papel_nome'):
                validation_errors.append(
                    f'A etapa "{etapa_nome}" usa o papel "{etapa.get("papel_nome")}", mas nenhum usuario com este papel esta vinculado a obra.'
                )
            else:
                validation_errors.append(
                    f'A etapa "{etapa_nome}" nao possui usuario definido na obra para executar o teste.'
                )
        elif not etapa.get('usuario_id'):
            validation_errors.append(
                f'A etapa "{etapa_nome}" nao possui aprovador definido para executar o teste.'
            )

    if validation_errors:
        history_html = _render_workflow_historico_execucoes_html(empresa_id, obra.id, view_mode=False)
        return jsonify({
            "ok": False,
            "error": "Nao foi possivel testar o workflow: " + " ".join(dict.fromkeys(validation_errors)),
            "preview": preview,
            "history_html": history_html,
        }), 400

    frente = (
        FrenteTrabalho.query
        .filter_by(empresa_id=empresa_id, obra_id=obra.id, ativo=True)
        .order_by(FrenteTrabalho.id.asc())
        .first()
    )
    if not frente:
        frente = (
            FrenteTrabalho.query
            .filter_by(empresa_id=empresa_id, obra_id=obra.id)
            .order_by(FrenteTrabalho.id.asc())
            .first()
        )
    if not frente:
        return jsonify({"ok": False, "error": "Cadastre pelo menos uma frente de trabalho para testar o workflow."}), 400

    try:
        rdo_teste = RDO(
            empresa_id=empresa_id,
            obra_id=obra.id,
            frente_trabalho_id=frente.id,
            data_rdo=date.today(),
            status='PENDENTE',
            ativo=False,
            criado_por=actor_id,
            modificado_por=actor_id,
        )
        db.session.add(rdo_teste)
        db.session.flush()

        execucao = WorkflowService.iniciar_execucao(
            rdo_id=rdo_teste.id,
            workflow_id=workflow.id,
            sobrescrever=True,
            origem='TESTE',
        )

        aprovacoes_pendentes = (
            RDOAprovacao.query
            .filter_by(rdo_id=rdo_teste.id, status='PENDENTE', ativo=True)
            .order_by(RDOAprovacao.nivel.asc(), RDOAprovacao.id.asc())
            .all()
        )
        nivel_atual = min((aprovacao.nivel for aprovacao in aprovacoes_pendentes), default=None)
        for aprovacao in aprovacoes_pendentes:
            if nivel_atual is not None and aprovacao.nivel != nivel_atual:
                continue
            NotificacaoService.criar_notificacao(
                empresa_id=empresa_id,
                usuario_id=aprovacao.aprovador_id,
                tipo=TipoNotificacao.APROVACAO_PENDENTE,
                titulo=f"Aprovacao Pendente: Workflow de teste da obra {obra.nome}",
                mensagem=f"O workflow de teste da obra '{obra.nome}' aguarda sua aprovacao.",
                link=url_for('auth.visualizar_rdo', rdo_id=rdo_teste.id),
                obra_id=obra.id,
                rdo_id=rdo_teste.id,
                criado_por=actor_id,
            )

        db.session.commit()
        history_html = _render_workflow_historico_execucoes_html(empresa_id, obra.id, view_mode=False)
        return jsonify({
            "ok": True,
            "message": "Workflow de teste iniciado com sucesso.",
            "execucao_id": execucao.id,
            "history_html": history_html,
        })
    except WorkflowResolucaoError as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "error": "Nao foi possivel iniciar o workflow de teste."}), 500


@auth_bp.post("/obras/<int:id>/workflow-execucoes/<int:execucao_id>/cancelar")
@login_required
@permission_required('obra.manage')
def cancelar_execucao_workflow_obra(id, execucao_id):
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return jsonify({"ok": False, "error": "Acesso negado para esta obra."}), 403

    empresa_id = session.get('empresa_id')
    execucao = WorkflowExecucao.query.filter_by(
        id=execucao_id,
        empresa_id=empresa_id,
        obra_id=id,
    ).first()
    if not execucao:
        return jsonify({"ok": False, "error": "Execucao nao encontrada."}), 404

    if execucao.ativo is False:
        return jsonify({"ok": False, "error": "Esta execucao ja foi encerrada e nao pode ser cancelada."}), 400

    if execucao.status not in {'PENDENTE', 'EM_ANDAMENTO', 'REABERTO'}:
        return jsonify({"ok": False, "error": "Somente fluxos em andamento podem ser cancelados."}), 400

    workflow_def = execucao.workflow or db.session.get(WorkflowDefinicao, execucao.workflow_id)
    if workflow_def and workflow_def.permite_cancelamento is False:
        return jsonify({"ok": False, "error": "Este workflow nao permite cancelamento."}), 400

    motivo = ((request.get_json(silent=True) or {}).get('motivo') or '').strip() or 'Fluxo cancelado manualmente.'
    ok, message = WorkflowService.cancelar_execucao(execucao.rdo_id, motivo=motivo, commit=True)
    if not ok:
        return jsonify({"ok": False, "error": message}), 400

    history_html = _render_workflow_historico_execucoes_html(empresa_id, id, view_mode=False)
    return jsonify({
        "ok": True,
        "message": message,
        "history_html": history_html,
    })


def _get_frente_or_404(frente_id: int):
    empresa_id = session.get("empresa_id")
    frente = FrenteTrabalho.query.filter_by(id=frente_id, empresa_id=empresa_id).first_or_404()

    scope_ids = get_user_scope_ids()
    if scope_ids is not None and frente.obra_id not in scope_ids:
        abort(403)

    return frente


def _serialize_frente_colaborador(vinculo: FrenteColaborador):
    colaborador = vinculo.colaborador
    return {
        "id": vinculo.id,
        "vinculo_id": vinculo.id,
        "colaborador_id": vinculo.colaborador_id,
        "colaborador_nome": colaborador.nome if colaborador else "",
        "cpf": (colaborador.cadastro_pessoa_fisica if colaborador else None),
        "colaborador_cpf": (colaborador.cadastro_pessoa_fisica if colaborador else None),
        "funcao_id": vinculo.funcao_id,
        "funcao_nome": vinculo.funcao.nome if vinculo.funcao else "",
        "data_inicio": vinculo.data_inicio.isoformat() if vinculo.data_inicio else None,
        "data_fim": vinculo.data_fim.isoformat() if vinculo.data_fim else None,
        "ativo": bool(vinculo.ativo),
        "observacao": getattr(vinculo, "observacao", None),
    }


def _frente_colaboradores_counts(frente_id: int, empresa_id: int):
    rows = (
        FrenteColaborador.query
        .filter(
            FrenteColaborador.frente_id == frente_id,
            FrenteColaborador.empresa_id == empresa_id,
        )
        .all()
    )
    total = len(rows)
    ativos = sum(1 for row in rows if bool(row.ativo))
    inativos = total - ativos
    return {"total": total, "ativos": ativos, "inativos": inativos}


@auth_bp.get("/api/frente/<int:frente_id>/colaboradores")
@login_required
def api_frente_colaboradores_list(frente_id):
    frente = _get_frente_or_404(frente_id)

    rows = (
        FrenteColaborador.query
        .filter(FrenteColaborador.frente_id == frente.id, FrenteColaborador.empresa_id == frente.empresa_id)
        .outerjoin(Colaborador, Colaborador.id == FrenteColaborador.colaborador_id)
        .order_by(func.coalesce(Colaborador.nome, FrenteColaborador.id).asc())
        .all()
    )

    items = [_serialize_frente_colaborador(row) for row in rows]
    counts = _frente_colaboradores_counts(frente.id, frente.empresa_id)

    return jsonify({
        "ok": True,
        "frente": {"id": frente.id, "obra_id": frente.obra_id, "nome": frente.nome},
        "counts": counts,
        "items": items,
    })


@auth_bp.get("/api/colaboradores/search")
@login_required
def api_colaboradores_search():
    empresa_id = session.get("empresa_id")
    q = (request.args.get("q") or "").strip()
    tipo = (request.args.get("tipo") or "").strip().upper()
    cpf = (request.args.get("cpf") or "").strip()

    query = Colaborador.query.filter(Colaborador.empresa_id == empresa_id)

    if q:
        query = query.filter(
            db.or_(
                Colaborador.nome.ilike(f"%{q}%"),
                Colaborador.cadastro_pessoa_fisica.ilike(f"%{q}%"),
            )
        )
    if cpf:
        query = query.filter(Colaborador.cadastro_pessoa_fisica.ilike(f"%{cpf}%"))
    if tipo in ("PROPRIO", "TERCEIRO", "CLIENTE"):
        query = query.filter(Colaborador.tipo == tipo)

    colaboradores = query.order_by(Colaborador.nome.asc()).limit(50).all()

    items = []
    for c in colaboradores:
        vinculo = (
            FrenteColaborador.query
            .filter(
                FrenteColaborador.empresa_id == empresa_id,
                FrenteColaborador.colaborador_id == c.id,
                FrenteColaborador.ativo.is_(True),
                FrenteColaborador.data_fim.is_(None),
            )
            .order_by(
                FrenteColaborador.data_inicio.is_(None),
                FrenteColaborador.data_inicio.desc(),
                FrenteColaborador.id.desc(),
            )
            .first()
        )
        items.append({
            "id": c.id,
            "nome": c.nome,
            "tipo": c.tipo,
            "cpf": c.cadastro_pessoa_fisica,
            "ativo": bool(c.ativo),
            "funcao_atual": vinculo.funcao.nome if (vinculo and vinculo.funcao) else None,
        })

    return jsonify({"ok": True, "items": items})


@auth_bp.post("/api/frente/<int:frente_id>/colaboradores")
@login_required
@permission_required("obra.manage")
def api_frente_colaboradores_create(frente_id):
    def _parse_date(value):
        value = (value or "").strip()
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    frente = _get_frente_or_404(frente_id)

    data = request.get_json(silent=True) or {}
    colaborador_id = data.get("colaborador_id")
    funcao_id = data.get("funcao_id")
    data_inicio = data.get("data_inicio")
    data_fim = data.get("data_fim")
    ativo = data.get("ativo", True)

    if not colaborador_id:
        return jsonify({"ok": False, "error": "Colaborador é obrigatório."}), 400

    colaborador = Colaborador.query.filter_by(id=colaborador_id, empresa_id=frente.empresa_id).first()
    if not colaborador:
        return jsonify({"ok": False, "error": "Colaborador inválido."}), 400

    novo = FrenteColaborador(
        empresa_id=frente.empresa_id,
        frente_id=frente.id,
        colaborador_id=int(colaborador_id),
        funcao_id=int(funcao_id) if funcao_id else None,
        data_inicio=_parse_date(data_inicio) if data_inicio else None,
        data_fim=_parse_date(data_fim) if data_fim else None,
        ativo=bool(ativo),
    )
    set_audit_on_create(novo)
    db.session.add(novo)
    db.session.commit()
    novo = (
        FrenteColaborador.query
        .filter_by(id=novo.id, empresa_id=frente.empresa_id)
        .outerjoin(Colaborador, Colaborador.id == FrenteColaborador.colaborador_id)
        .first()
    )
    return jsonify({
        "ok": True,
        "id": novo.id,
        "item": _serialize_frente_colaborador(novo),
        "counts": _frente_colaboradores_counts(frente.id, frente.empresa_id),
    })


@auth_bp.put("/api/frente-colaborador/<int:vinculo_id>")
@login_required
@permission_required("obra.manage")
def api_frente_colaborador_update(vinculo_id):
    def _parse_date(value):
        value = (value or "").strip()
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    empresa_id = session.get("empresa_id")
    vinculo = FrenteColaborador.query.filter_by(id=vinculo_id, empresa_id=empresa_id).first_or_404()
    _get_frente_or_404(vinculo.frente_id)

    data = request.get_json(silent=True) or {}
    vinculo.funcao_id = int(data.get("funcao_id")) if data.get("funcao_id") else None
    vinculo.data_inicio = _parse_date(data.get("data_inicio")) if data.get("data_inicio") else None
    vinculo.data_fim = _parse_date(data.get("data_fim")) if data.get("data_fim") else None
    vinculo.ativo = bool(data.get("ativo", vinculo.ativo))
    set_audit_on_update(vinculo)

    db.session.commit()
    return jsonify({
        "ok": True,
        "item": _serialize_frente_colaborador(vinculo),
        "counts": _frente_colaboradores_counts(vinculo.frente_id, vinculo.empresa_id),
    })


@auth_bp.post("/api/frente-colaborador/<int:vinculo_id>/toggle")
@login_required
@permission_required("obra.manage")
def api_frente_colaborador_toggle(vinculo_id):
    empresa_id = session.get("empresa_id")
    vinculo = FrenteColaborador.query.filter_by(id=vinculo_id, empresa_id=empresa_id).first_or_404()
    _get_frente_or_404(vinculo.frente_id)

    vinculo.ativo = not bool(vinculo.ativo)
    if vinculo.ativo and vinculo.data_fim is not None:
        vinculo.data_fim = None
    elif not vinculo.ativo and vinculo.data_fim is None:
        vinculo.data_fim = datetime.utcnow().date()
    set_audit_on_update(vinculo)
    db.session.commit()
    return jsonify({
        "ok": True,
        "ativo": bool(vinculo.ativo),
        "item": _serialize_frente_colaborador(vinculo),
        "counts": _frente_colaboradores_counts(vinculo.frente_id, vinculo.empresa_id),
    })

@auth_bp.post("/obra/toggle-status/<int:id>")
@auth_bp.post("/obras/<int:id>/toggle-ativo")
@login_required
@permission_required('obra.manage')
def toggle_obra_status(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return '', 403

    empresa_id = session.get('empresa_id')
    obra = Obra.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
    if obra.status == 1: obra.status = 0
    else: obra.status = 1
    set_audit_on_update(obra)
    try:
        db.session.commit()
        return '', 200
    except Exception:
        db.session.rollback()
        return '', 500
