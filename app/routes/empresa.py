from app.routes.auth_common import *
from collections import defaultdict
from datetime import datetime

from app.services.config_service import ConfigService
from app.models.configuracao import ConfigDefinicao, EmpresaConfig
from app.models.usuario import Papel, Permissao, PapelPermissao, UsuarioPapel
from app.models.workflow import WorkflowDefinicao, WorkflowEtapa, WorkflowExecucao, WorkflowExecucaoEtapa, WorkflowGrupo
from app.models.obra import Obra, ObraUsuario
from app.models.usuario import Usuario
from app.services.workflow_service import WorkflowService


def _ensure_workflow_default_definition():
    definicao = ConfigDefinicao.query.filter_by(chave='workflow.default').first()
    if definicao:
        return definicao

    definicao = ConfigDefinicao(
        chave='workflow.default',
        descricao='Workflow padrão da empresa',
        tipo='STRING',
        valor_padrao='SIMPLES',
        is_system=True,
    )
    db.session.add(definicao)
    db.session.flush()
    return definicao


def _formatar_data_workflow(datahora):
    if not datahora:
        return 'Sem registro'

    agora = datetime.now()
    if datahora.date() == agora.date():
        return f"Hoje às {datahora.strftime('%H:%M')}"

    return datahora.strftime('%d/%m/%Y às %H:%M')


def _formatar_duracao_media(segundos_total, quantidade):
    if not quantidade or segundos_total <= 0:
        return 'Sem histórico'

    media_segundos = segundos_total / quantidade
    dias = int(media_segundos // 86400)
    horas = int((media_segundos % 86400) // 3600)
    minutos = int((media_segundos % 3600) // 60)

    if dias > 0:
        return f'{dias}d {horas}h'
    if horas > 0:
        return f'{horas}h{minutos:02d}m'
    return f'{max(minutos, 1)}min'


def _formatar_duracao_execucao_workflow(inicio, fim=None, status=None):
    if not inicio:
        return 'Sem duração'

    fim_calculo = fim or datetime.now()
    segundos = max(int((fim_calculo - inicio).total_seconds()), 0)
    dias = segundos // 86400
    horas = (segundos % 86400) // 3600
    minutos = (segundos % 3600) // 60

    if dias:
        duracao = f'{dias}d {horas}h'
    elif horas:
        duracao = f'{horas}h {minutos:02d}min'
    elif minutos:
        duracao = f'{minutos}min'
    else:
        duracao = 'menos de 1min'

    if (status or '').upper() in {'PENDENTE', 'EM_ANDAMENTO', 'REABERTO'} and not fim:
        return f'Em execução há {duracao}'
    return duracao


def _build_empresa_modal_workflow_history(execucoes_obra, detalhes_url):
    execucoes_ordenadas = sorted(
        execucoes_obra,
        key=lambda execucao: (
            execucao.iniciado_em or execucao.criado_em or datetime.min,
            execucao.id or 0,
        ),
        reverse=True,
    )

    historico = []
    for execucao in execucoes_ordenadas[:20]:
        inicio = execucao.iniciado_em or execucao.criado_em
        status_code = (execucao.status or 'PENDENTE').upper()
        status_meta = _normalize_workflow_status(status_code)
        workflow_snapshot = execucao.workflow_snapshot or {}
        requester = getattr(execucao.rdo, 'usuario', None) if execucao.rdo else None
        requester_name = (
            getattr(requester, 'nome', None)
            or getattr(execucao.criador, 'nome', None)
            or 'Não identificado'
        )
        ano_execucao = (inicio or datetime.now()).year

        historico.append({
            'id': execucao.id,
            'execution_number': f'{ano_execucao}-{execucao.id:06d}',
            'status': status_code,
            'status_label': status_meta['label'],
            'status_badge_class': status_meta['badge_class'],
            'status_dot_class': status_meta['dot_class'],
            'started_at_label': _formatar_data_workflow(inicio),
            'duration_label': _formatar_duracao_execucao_workflow(
                inicio,
                execucao.finalizado_em,
                status_code,
            ),
            'requester_name': requester_name,
            'workflow_name': workflow_snapshot.get('nome') or getattr(execucao.workflow, 'nome', None) or 'Workflow não identificado',
            'detalhes_url': detalhes_url,
        })

    return historico


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
        "label": normalized.title() if normalized else "Sem execução",
        "badge_class": "border-slate-200 bg-slate-100 text-slate-700",
        "dot_class": "bg-slate-400",
        "icon": "fa-circle-question",
    })


def _workflow_diagram_variant(workflow):
    if not workflow:
        return 'default'
    tipo_fluxo = (workflow.tipo_fluxo or '').upper()
    return 'parallel' if workflow.aprovacao_paralela or tipo_fluxo == 'PARALELO' else 'default'


def _normalizar_regra_aprovacao_grupo(valor):
    regra = (valor or 'TODOS')
    regra = str(regra).strip().upper()
    return 'QUALQUER' if regra in {'QUALQUER', 'PRIMEIRO', 'OU'} else 'TODOS'


def _workflow_template_payload(workflow, *, origem_label=None, origem_tipo=None, is_default=False):
    if not workflow:
        return {}

    return {
        'workflow_id': workflow.id,
        'workflow_codigo': workflow.codigo,
        'workflow_nome': workflow.nome,
        'workflow_descricao': workflow.descricao,
        'tipo_fluxo': workflow.tipo_fluxo or 'CONFIGURAVEL',
        'aprovacao_paralela': bool(workflow.aprovacao_paralela),
        'rejeicao_cancela_fluxo': bool(workflow.rejeicao_cancela_fluxo),
        'cliente_obrigatorio': bool(workflow.cliente_obrigatorio),
        'assinatura_obrigatoria': bool(workflow.assinatura_obrigatoria),
        'permite_reprovar': bool(workflow.permite_reprovar),
        'comentario_reprovacao_obrigatorio': bool(workflow.comentario_reprovacao_obrigatorio),
        'sla_horas': workflow.sla_horas,
        'sla_global_horas': workflow.sla_global_horas,
        'permite_reabertura': bool(workflow.permite_reabertura),
        'permite_cancelamento': bool(workflow.permite_cancelamento),
        'ativo': bool(workflow.ativo),
        'is_default': bool(is_default),
        'workflow_origem': origem_label or ('Padrao da Empresa' if is_default else 'Workflow da Empresa'),
        'workflow_origem_tipo': origem_tipo or 'empresa',
        'workflow_diagram_variant': _workflow_diagram_variant(workflow),
        'regra_etapa': 'TODOS',
        'criado_por': workflow.criado_por,
        'modificado_por': workflow.modificado_por,
        'criado_em_label': _formatar_data_workflow(workflow.criado_em),
        'modificado_em_label': _formatar_data_workflow(workflow.modificado_em),
    }


def _workflow_etapa_template_payload(etapa, *, workflow=None, index=0, tempo_medio=None):
    tipo_aprovador = etapa.tipo_aprovador or 'USUARIO'
    papel_nome = etapa.papel.nome if etapa.papel else None
    usuario_nome = etapa.usuario_aprovador.nome if etapa.usuario_aprovador else None

    grupo = etapa.grupo
    regra_aprovacao = _normalizar_regra_aprovacao_grupo(
        grupo.regra_aprovacao if grupo else None
    )

    return {
        'etapa_id': etapa.id,
        'workflow_id': etapa.workflow_id,
        'nivel': etapa.nivel,
        'ordem': etapa.ordem,
        'codigo': etapa.codigo,
        'nome': etapa.nome,
        'tipo': tipo_aprovador,
        'tipo_aprovador': tipo_aprovador,
        'papel': papel_nome or usuario_nome or etapa.nome,
        'papel_id': etapa.papel_id,
        'papel_codigo': etapa.papel_codigo,
        'papel_nome': papel_nome,
        'usuario_aprovador_id': etapa.usuario_aprovador_id,
        'usuario_nome': usuario_nome,
        'grupo_id': etapa.grupo_id,
        'grupo_nome': grupo.nome if grupo else None,
        'regra_aprovacao': regra_aprovacao,
        'grupo_paralelo': etapa.grupo_paralelo,
        'workflow_group': etapa.grupo_paralelo or etapa.nivel or index + 1,
        'obrigatorio': bool(etapa.obrigatorio),
        'obrigatoria': bool(etapa.obrigatoria),
        'assinatura_obrigatoria': bool(etapa.assinatura_obrigatoria),
        'sla_horas': etapa.sla_horas,
        'permite_reprovar': bool(etapa.permite_reprovar),
        'comentario_reprovacao_obrigatorio': bool(etapa.comentario_reprovacao_obrigatorio),
        'ativo': bool(etapa.ativo),
        'regra_etapa': regra_aprovacao,
        'tempo_medio': tempo_medio if tempo_medio is not None else 'Sem histórico',
        'criado_por': etapa.criado_por,
        'modificado_por': etapa.modificado_por,
        'criado_em_label': _formatar_data_workflow(etapa.criado_em),
        'modificado_em_label': _formatar_data_workflow(etapa.modificado_em),
    }


def _build_empresa_workflow_editor_context(empresa_id, workflows_empresa_padrao, workflow_default):
    role_options = []
    user_options = []
    workflow_previews = {}
    default_workflow_id = workflow_default.id if workflow_default else None

    if not empresa_id:
        return role_options, user_options, workflow_previews, default_workflow_id

    papeis = (
        Papel.query
        .filter(
            Papel.ativo.is_(True),
            db.or_(Papel.empresa_id == empresa_id, Papel.empresa_id.is_(None)),
        )
        .order_by(Papel.empresa_id.is_(None), Papel.nome.asc())
        .all()
    )
    role_options = [{"id": papel.id, "nome": papel.nome} for papel in papeis]

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

    user_options = [
        {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "papel_ids": sorted(papeis_por_usuario.get(usuario.id, set())),
        }
        for usuario in usuarios_empresa
    ]

    for workflow in workflows_empresa_padrao:
        etapas_preview = WorkflowService.obter_etapas_ordenadas(workflow.id)
        grupos_preview = (
            WorkflowGrupo.query
            .filter_by(workflow_id=workflow.id, ativo=True)
            .order_by(WorkflowGrupo.ordem.asc(), WorkflowGrupo.id.asc())
            .all()
        )
        is_default = workflow.id == default_workflow_id
        workflow_previews[str(workflow.id)] = {
            **_workflow_template_payload(
                workflow,
                origem_label="Padrao da Empresa" if is_default else "Workflow da Empresa",
                origem_tipo="empresa",
                is_default=is_default,
            ),
            "grupos": [
                {
                    "id": grupo.id,
                    "nome": grupo.nome,
                    "ordem": grupo.ordem,
                    "regra_aprovacao": _normalizar_regra_aprovacao_grupo(grupo.regra_aprovacao),
                }
                for grupo in grupos_preview
            ],
            "etapas": [
                _workflow_etapa_template_payload(etapa, workflow=workflow, index=index)
                for index, etapa in enumerate(etapas_preview)
            ],
            "valid": True,
            "errors": [],
        }

    return role_options, user_options, workflow_previews, default_workflow_id

#######################################################################################################
####################################################################################################### Empresa
#######################################################################################################

@auth_bp.app_context_processor
def inject_company_info():
    def _company_defaults(usuario=None):
        return dict(
            nome_empresa="Não logado" if usuario is None else "Não definida",
            logo_empresa="logo/logo_sistema.png",
            icone_empresa="logo/icone_sistema.png",
            usuario_atual=usuario,
        )

    try:
        is_authenticated = current_user.is_authenticated
    except Exception:
        return _company_defaults()

    if is_authenticated:
        empresa_db = None
        try:
            empresa_id = getattr(current_user, "empresa_id", None)
        except Exception:
            return _company_defaults()

        if empresa_id is not None:
            empresa_db = db.session.get(Empresa, empresa_id)

        nome = empresa_db.nome if empresa_db is not None else "Não definida"

        # Logos da empresa (fallback para o sistema)
        logo_empresa = (
            empresa_db.logo_empresa
            if empresa_db is not None and empresa_db.logo_empresa
            else 'logo/logo_sistema.png'
        )
        icone_empresa = (
            empresa_db.icone_empresa
            if empresa_db is not None and empresa_db.icone_empresa
            else 'logo/icone_sistema.png'
        )

        return dict(
            nome_empresa=nome,
            logo_empresa=logo_empresa,
            icone_empresa=icone_empresa,
            usuario_atual=current_user
        )

    return _company_defaults()

def _build_empresa_page_context(empresa_id, *, can_edit=False, start_in_edit_mode=False):
    empresa_db = Empresa.query.filter_by(id=empresa_id).first()
    config_data = {
        'id': empresa_db.id if empresa_db else None,
        'nome': empresa_db.nome if empresa_db else '',
        'logo_path': empresa_db.logo_empresa if empresa_db and empresa_db.logo_empresa else 'logo/logo_sistema.png',
        'icone_path': empresa_db.icone_empresa if empresa_db and empresa_db.icone_empresa else 'logo/icone_sistema.png',
        'data_expiracao': getattr(empresa_db, 'data_expiracao', None) if empresa_db else None,
        'criado_em': empresa_db.criado_em if empresa_db else None,
        'modificado_em': empresa_db.modificado_em if empresa_db else None,
    }

    # Mapa de configurações resolvidas (Obra não considerado aqui)
    try:
        mapa = ConfigService.obter_mapa_config(empresa_id=empresa_id, obra_id=None)
    except Exception:
        mapa = {}

    # Definições e papéis para edição via UI
    definicoes = ConfigDefinicao.query.order_by(ConfigDefinicao.chave).all()
    papeis_globais = Papel.query.filter_by(empresa_id=None).order_by(Papel.nome).all()
    papeis_empresa = Papel.query.filter_by(empresa_id=empresa_id).order_by(Papel.nome).all()
    papeis_workflow = Papel.query.filter(
        or_(Papel.empresa_id == empresa_id, Papel.empresa_id.is_(None)),
        Papel.ativo.is_(True),
    ).order_by(Papel.nome).all()
    usuarios_empresa = Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(Usuario.email.asc()).all()
    workflows = WorkflowDefinicao.query.filter_by(empresa_id=empresa_id).order_by(WorkflowDefinicao.nome).all()
    workflows_empresa_padrao = [
        workflow
        for workflow in workflows
        if workflow.obra_id is None and workflow.ativo
    ]
    workflow_default_codigo = (
        mapa.get('workflow.default')
        if mapa.get('workflow.default')
        else 'SIMPLES'
    )
    obras = Obra.query.filter_by(empresa_id=empresa_id).order_by(Obra.nome).all()
    permissoes_disponiveis = Permissao.query.filter((Permissao.empresa_id == empresa_id) | (Permissao.empresa_id.is_(None))).order_by(Permissao.chave).all()
    workflow_default = WorkflowService._resolver_workflow_empresa_padrao(empresa_id) if empresa_id else None
    workflow_role_options, workflow_user_options, workflow_preview_by_id, workflow_default_id = _build_empresa_workflow_editor_context(
        empresa_id,
        workflows_empresa_padrao,
        workflow_default,
    )
    workflow_default_ultima_edicao = _formatar_data_workflow(
        (workflow_default.modificado_em or workflow_default.criado_em) if workflow_default else None
    )
    workflow_etapas_map = {
        workflow.id: WorkflowService.obter_etapas_ordenadas(workflow.id)
        for workflow in workflows
    }
    workflow_execucoes = (
        WorkflowExecucao.query
        .filter_by(empresa_id=empresa_id)
        .order_by(
            WorkflowExecucao.ativo.desc(),
            WorkflowExecucao.iniciado_em.desc(),
            WorkflowExecucao.id.desc(),
        )
        .limit(12)
        .all()
    )
    workflow_execucoes_all = WorkflowExecucao.query.filter_by(empresa_id=empresa_id).all()
    workflow_execucao_etapas_pendentes = WorkflowExecucaoEtapa.query.filter_by(
        empresa_id=empresa_id,
        ativo=True,
        status='PENDENTE',
    ).all()
    workflow_execucao_etapas_aprovadas = WorkflowExecucaoEtapa.query.filter_by(
        empresa_id=empresa_id,
        ativo=True,
        status='APROVADO',
    ).all()

    workflow_status_counts = {
        status: 0
        for status in ['PENDENTE', 'EM_ANDAMENTO', 'APROVADO', 'REJEITADO', 'CANCELADO', 'REABERTO']
    }
    for execucao in workflow_execucoes_all:
        workflow_status_counts[execucao.status] = workflow_status_counts.get(execucao.status, 0) + 1

    workflow_obras_map = {
        workflow.obra_id: workflow
        for workflow in workflows
        if workflow.obra_id is not None and workflow.ativo
    }
    obras_workflow_resumo = []
    obras_herdando_total = 0
    for obra in obras:
        workflow_obra = workflow_obras_map.get(obra.id)
        workflow_resolvido = workflow_obra or workflow_default
        herda_empresa = workflow_obra is None and workflow_default is not None
        if herda_empresa:
            obras_herdando_total += 1
        obras_workflow_resumo.append({
            'obra': obra,
            'workflow': workflow_resolvido,
            'workflow_proprio': workflow_obra,
            'herda_empresa': herda_empresa,
            'tem_workflow': workflow_resolvido is not None,
            'etapas_total': len(workflow_etapas_map.get(workflow_resolvido.id, [])) if workflow_resolvido else 0,
        })

    workflow_metricas = {
        'total_definicoes': len(workflows),
        'ativos_empresa': len(workflows_empresa_padrao),
        'ativos_obra': sum(1 for workflow in workflows if workflow.obra_id is not None and workflow.ativo),
        'obras_herdando': obras_herdando_total,
        'obras_utilizando': sum(1 for resumo in obras_workflow_resumo if resumo['tem_workflow']),
        'execucoes_total': len(workflow_execucoes_all),
        'execucoes_ativas': sum(1 for execucao in workflow_execucoes_all if execucao.status in {'PENDENTE', 'EM_ANDAMENTO', 'REABERTO'}),
        'execucoes_concluidas': sum(1 for execucao in workflow_execucoes_all if execucao.status == 'APROVADO'),
        'execucoes_rejeitadas': sum(1 for execucao in workflow_execucoes_all if execucao.status == 'REJEITADO'),
        'pendencias_aprovacao': len(workflow_execucao_etapas_pendentes),
    }

    workflows_resumo = []
    for workflow in workflows:
        etapas = workflow_etapas_map.get(workflow.id, [])
        is_default = workflow_default is not None and workflow.id == workflow_default.id
        workflows_resumo.append({
            'item': workflow,
            'etapas': etapas,
            'etapas_total': len(etapas),
            'is_default': is_default,
            'escopo_label': workflow.obra.nome if workflow.obra_id and workflow.obra else 'Empresa',
            'escopo_tipo': 'obra' if workflow.obra_id else 'empresa',
        })

    medias_etapa = {}
    acumulado_etapa = defaultdict(lambda: {'segundos': 0.0, 'count': 0})
    for etapa_execucao in workflow_execucao_etapas_aprovadas:
        if not etapa_execucao.etapa_definicao_id or not etapa_execucao.aprovado_em or not etapa_execucao.criado_em:
            continue
        duracao = (etapa_execucao.aprovado_em - etapa_execucao.criado_em).total_seconds()
        if duracao < 0:
            continue
        bucket = acumulado_etapa[etapa_execucao.etapa_definicao_id]
        bucket['segundos'] += duracao
        bucket['count'] += 1

    for etapa_id, dados in acumulado_etapa.items():
        media_horas = (dados['segundos'] / dados['count']) / 3600 if dados['count'] else 0
        if media_horas >= 24:
            medias_etapa[etapa_id] = f"{media_horas / 24:.1f} dias médio"
        elif media_horas > 0:
            medias_etapa[etapa_id] = f"{media_horas:.1f} h média"
        else:
            medias_etapa[etapa_id] = 'Sem média'

    obra_usuario_relacoes = ObraUsuario.query.filter_by(empresa_id=empresa_id, ativo=True).all()
    relacoes_por_obra = defaultdict(list)
    relacoes_por_papel = defaultdict(list)
    for relacao in obra_usuario_relacoes:
        relacoes_por_obra[relacao.obra_id].append(relacao)
        if relacao.papel_id:
            relacoes_por_papel[relacao.papel_id].append(relacao)

    workflow_matriz_responsabilidades = []
    if workflow_default:
        for etapa in workflow_etapas_map.get(workflow_default.id, []):
            papel_id = etapa.papel_id or (etapa.papel.id if etapa.papel else None)
            relacoes_papel = relacoes_por_papel.get(papel_id, [])
            obras_vinculadas = len({rel.obra_id for rel in relacoes_papel if rel.obra_id})
            usuario_atual = next(
                (rel.colaborador for rel in relacoes_papel if rel.colaborador and rel.colaborador.ativo),
                None,
            )

            if etapa.tipo_aprovador == 'RESPONSAVEL_OBRA':
                workflow_matriz_responsabilidades.append({
                    'papel': etapa.nome,
                    'responsavel_atual': 'Responsáveis por obra',
                    'obras_vinculadas': len([obra for obra in obras if obra.usuario_responsavel]),
                })
                continue

            if etapa.usuario_aprovador:
                workflow_matriz_responsabilidades.append({
                    'papel': etapa.nome,
                    'responsavel_atual': etapa.usuario_aprovador.nome,
                    'obras_vinculadas': len(obras_workflow_resumo),
                })
                continue

            workflow_matriz_responsabilidades.append({
                'papel': etapa.papel.nome if etapa.papel else etapa.nome,
                'responsavel_atual': usuario_atual.nome if usuario_atual else 'Não vinculado',
                'obras_vinculadas': obras_vinculadas,
            })

    workflow_default_etapas_resumo = []
    if workflow_default:
        for index, etapa in enumerate(workflow_etapas_map.get(workflow_default.id, [])):
            workflow_default_etapas_resumo.append(
                _workflow_etapa_template_payload(
                    etapa,
                    workflow=workflow_default,
                    index=index,
                    tempo_medio=medias_etapa.get(etapa.id, 'Sem histórico'),
                )
            )

    obras_modal_payload = []
    for resumo in obras_workflow_resumo:
        obra = resumo['obra']
        workflow_resolvido = resumo['workflow']
        etapas_resolvidas = workflow_etapas_map.get(workflow_resolvido.id, []) if workflow_resolvido else []
        execucoes_obra = [
            execucao for execucao in workflow_execucoes_all
            if execucao.obra_id == obra.id
        ]
        execucoes_ativas_obra = [
            execucao for execucao in execucoes_obra
            if execucao.status in {'PENDENTE', 'EM_ANDAMENTO', 'REABERTO'}
        ]
        status_counts_obra = defaultdict(int)
        for execucao in execucoes_obra:
            status_counts_obra[execucao.status or 'SEM_EXECUCAO'] += 1
        status_breakdown_obra = []
        for status, total in sorted(status_counts_obra.items(), key=lambda item: (-item[1], item[0] or '')):
            status_info = _normalize_workflow_status(status)
            status_breakdown_obra.append({
                'status': status_info['label'],
                'status_code': status,
                'total': total,
                'badge_class': status_info['badge_class'],
                'dot_class': status_info['dot_class'],
                'icon': status_info['icon'],
            })
        ultima_execucao = sorted(
            execucoes_obra,
            key=lambda execucao: (
                execucao.iniciado_em or execucao.criado_em or datetime.min,
                execucao.id or 0,
            ),
            reverse=True,
        )[0] if execucoes_obra else None
        status_meta = _normalize_workflow_status(ultima_execucao.status if ultima_execucao else None)
        execucoes_concluidas_obra = [
            execucao for execucao in execucoes_obra
            if execucao.finalizado_em and execucao.iniciado_em
        ]

        duracao_total_segundos = 0
        for execucao in execucoes_concluidas_obra:
            duracao = (execucao.finalizado_em - execucao.iniciado_em).total_seconds()
            if duracao > 0:
                duracao_total_segundos += duracao

        execucoes_por_dia = defaultdict(lambda: {'execucoes': 0, 'erros': 0})
        for execucao in execucoes_obra:
            data_base = execucao.iniciado_em or execucao.criado_em
            if not data_base:
                continue
            bucket = execucoes_por_dia[data_base.date()]
            bucket['execucoes'] += 1
            if execucao.status in {'REJEITADO', 'CANCELADO'}:
                bucket['erros'] += 1

        dias_com_execucao = sorted(execucoes_por_dia.keys())[-5:]
        timeline_execucoes = [
            {
                'label': dia.strftime('%d/%m'),
                'value': execucoes_por_dia[dia]['execucoes'],
            }
            for dia in dias_com_execucao
        ]
        timeline_erros = [
            {
                'label': dia.strftime('%d/%m'),
                'value': execucoes_por_dia[dia]['erros'],
            }
            for dia in dias_com_execucao
        ]

        matriz_obra = []
        for etapa in etapas_resolvidas:
            usuario_nome = 'Não definido'
            if etapa.usuario_aprovador:
                usuario_nome = etapa.usuario_aprovador.nome
            elif etapa.tipo_aprovador == 'RESPONSAVEL_OBRA':
                usuario_nome = obra.usuario_responsavel.nome if obra.usuario_responsavel else 'Não definido'
            elif etapa.papel_id or etapa.papel:
                papel_id = etapa.papel_id or (etapa.papel.id if etapa.papel else None)
                relacao = next(
                    (rel for rel in relacoes_por_obra.get(obra.id, []) if rel.papel_id == papel_id and rel.colaborador),
                    None,
                )
                if relacao and relacao.colaborador:
                    usuario_nome = relacao.colaborador.nome
                else:
                    usuario_nome = 'Não vinculado'

            matriz_obra.append({
                'papel': etapa.papel.nome if etapa.papel else etapa.nome,
                'usuario': usuario_nome,
            })

        obra_workflow_url = f"{url_for('auth.editar_obra', id=obra.id, tab='workflow')}#workflow"
        obra_workflow_historico_url = f"{url_for('auth.editar_obra', id=obra.id, tab='workflow-historico')}#workflow"
        workflow_origem_label = 'Herdado da Empresa' if resumo['herda_empresa'] else ('Workflow Próprio da Obra' if resumo['workflow_proprio'] else 'Sem definição')
        workflow_origem_tipo = 'empresa' if resumo['herda_empresa'] else ('obra' if resumo['workflow_proprio'] else 'indefinido')
        workflow_payload = _workflow_template_payload(
            workflow_resolvido,
            origem_label=workflow_origem_label,
            origem_tipo=workflow_origem_tipo,
            is_default=bool(workflow_default and workflow_resolvido and workflow_resolvido.id == workflow_default.id),
        ) if workflow_resolvido else {}

        obras_modal_payload.append({
            'obra_id': obra.id,
            'obra_nome': obra.nome,
            'obra_workflow_url': obra_workflow_url,
            'obra_workflow_historico_url': obra_workflow_historico_url,
            **workflow_payload,
            'workflow_nome': workflow_resolvido.nome if workflow_resolvido else 'Sem workflow',
            'workflow_origem': workflow_origem_label,
            'workflow_origem_tipo': workflow_origem_tipo,
            'workflow_tipo_resumo': 'Herdado' if resumo['herda_empresa'] else 'Próprio',
            'responsavel': obra.usuario_responsavel.nome if obra.usuario_responsavel else 'Não definido',
            'execucoes_ativas': len(execucoes_ativas_obra),
            'execucoes_total': len(execucoes_obra),
            'execucoes_status': status_breakdown_obra,
            'matriz_total': len(matriz_obra),
            'duracao_media_fluxo': _formatar_duracao_media(duracao_total_segundos, len(execucoes_concluidas_obra)),
            'status': status_meta['label'],
            'status_code': (ultima_execucao.status if ultima_execucao else 'SEM_EXECUCAO'),
            'status_badge_class': status_meta['badge_class'],
            'status_dot_class': status_meta['dot_class'],
            'status_icon': status_meta['icon'],
            'ultima_atualizacao': _formatar_data_workflow(
                (workflow_resolvido.modificado_em or workflow_resolvido.criado_em) if workflow_resolvido else None
            ),
            'matriz': matriz_obra,
            'workflow_historico': _build_empresa_modal_workflow_history(
                execucoes_obra,
                obra_workflow_historico_url,
            ),
            'workflow_etapas': [
                _workflow_etapa_template_payload(
                    etapa,
                    workflow=workflow_resolvido,
                    index=index,
                    tempo_medio=medias_etapa.get(etapa.id, 'Sem histórico'),
                )
                for index, etapa in enumerate(etapas_resolvidas)
            ],
            'timeline_execucoes': timeline_execucoes,
            'timeline_erros': timeline_erros,
        })

    return {
        'config_data': config_data,
        'view_mode': not start_in_edit_mode,
        'empresa_view_url': url_for('auth.visualizar_empresa', id=empresa_id),
        'empresa_edit_url': url_for('auth.editar_empresa', id=empresa_id) if can_edit else None,
        'config_map': mapa,
        'definicoes': definicoes,
        'papeis_globais': papeis_globais,
        'papeis_empresa': papeis_empresa,
        'papeis_workflow': papeis_workflow,
        'usuarios_empresa': usuarios_empresa,
        'workflows': workflows,
        'workflows_resumo': workflows_resumo,
        'workflows_empresa_padrao': workflows_empresa_padrao,
        'workflow_default_codigo': workflow_default_codigo,
        'workflow_default': workflow_default,
        'workflow_default_ultima_edicao': workflow_default_ultima_edicao,
        'workflow_default_etapas': workflow_etapas_map.get(workflow_default.id, []) if workflow_default else [],
        'workflow_default_etapas_resumo': workflow_default_etapas_resumo,
        'workflow_execucoes': workflow_execucoes,
        'workflow_status_counts': workflow_status_counts,
        'workflow_metricas': workflow_metricas,
        'workflow_matriz_responsabilidades': workflow_matriz_responsabilidades,
        'workflow_role_options': workflow_role_options,
        'workflow_user_options': workflow_user_options,
        'workflow_preview_by_id': workflow_preview_by_id,
        'workflow_default_id': workflow_default_id,
        'obras_workflow_resumo': obras_workflow_resumo,
        'obras_modal_payload': obras_modal_payload,
        'obras': obras,
        'permissoes_disponiveis': permissoes_disponiveis,
        'can_edit': can_edit,
        'start_in_edit_mode': start_in_edit_mode,
    }


def _render_empresa_page(empresa_id, *, can_edit=False, start_in_edit_mode=False):
    return render_template(
        'empresa/empresa.html',
        **_build_empresa_page_context(
            empresa_id,
            can_edit=can_edit,
            start_in_edit_mode=start_in_edit_mode,
        ),
    )


def _user_can_manage_empresa():
    user = get_current_user()
    if not user:
        return False
    try:
        return bool(user.tem_permissao('empresa.manage'))
    except Exception:
        return False


@auth_bp.get("/empresa")
@login_required
def empresa():
    empresa_id = session.get('empresa_id')
    if not empresa_id:
        abort(404)
    return redirect(url_for('auth.visualizar_empresa', id=empresa_id))


@auth_bp.get("/empresa/<int:id>")
@login_required
def visualizar_empresa(id):
    empresa_id = session.get('empresa_id')
    user = get_current_user()
    if not user:
        abort(403)

    if not getattr(user, "is_admin", False) and id != empresa_id:
        abort(403)

    return _render_empresa_page(
        id,
        can_edit=_user_can_manage_empresa(),
        start_in_edit_mode=False,
    )


@auth_bp.get("/empresa/<int:id>/editar")
@login_required
@permission_required('empresa.manage')
def editar_empresa(id):
    empresa_id = session.get('empresa_id')
    user = get_current_user()
    if not user:
        abort(403)

    if not getattr(user, "is_admin", False) and id != empresa_id:
        abort(403)

    return _render_empresa_page(
        id,
        can_edit=True,
        start_in_edit_mode=True,
    )

@auth_bp.route('/salvar-empresa', methods=['POST'])
@auth_bp.post('/empresa/<int:id>/salvar')
@login_required
@permission_required('empresa.manage')
def salvar_empresa(id=None):
    nome_empresa = request.form.get('nome_empresa')
    logo_file = request.files.get('logo_empresa')
    icone_file = request.files.get('icone_empresa')
    empresa_id = id or session.get('empresa_id')

    user = get_current_user()
    if not user:
        abort(403)
    if not getattr(user, "is_admin", False) and empresa_id != session.get('empresa_id'):
        abort(403)

    try:
        empresa_db = Empresa.query.get(empresa_id)
        if not empresa_db:
            empresa_db = Empresa(nome=nome_empresa)
            db.session.add(empresa_db)
            db.session.flush()
        else:
            empresa_db.nome = nome_empresa
        
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        if logo_file and logo_file.filename != '':
            if allowed_file(logo_file.filename):
                ext = logo_file.filename.rsplit('.', 1)[1].lower()
                logo_filename = f"logo_empresa_{empresa_db.id}.{ext}"
                logo_file.save(os.path.join(upload_folder, logo_filename))
                empresa_db.logo_empresa = f"uploads/logos/{logo_filename}"

        if icone_file and icone_file.filename != '':
            if allowed_file(icone_file.filename):
                ext = icone_file.filename.rsplit('.', 1)[1].lower()
                icone_filename = f"icone_empresa_{empresa_db.id}.{ext}"
                icone_file.save(os.path.join(upload_folder, icone_filename))
                empresa_db.icone_empresa = f"uploads/logos/{icone_filename}"

        db.session.commit()
        flash('Configurações da empresa atualizadas com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar configurações: {str(e)}', 'danger')

    return redirect(url_for('auth.editar_empresa', id=empresa_id))


# ---------------------------------------------------------------------------
# API: atualização inline de configurações da empresa (AJAX)
# Este endpoint substitui a antiga rota em /admin para permitir que
# admins de empresa usem apenas a UI em /auth/empresa
# ---------------------------------------------------------------------------


@auth_bp.post('/empresa/api_config')
@login_required
@permission_required('config.manage')
def api_update_empresa_config():
    empresa_id = session.get('empresa_id')
    if not empresa_id:
        return jsonify({'ok': False, 'error': 'empresa não identificada'}), 403

    data = request.get_json() or {}
    chave = data.get('chave')
    valor = data.get('valor')

    if not chave:
        return jsonify({'ok': False, 'error': 'chave é obrigatória'}), 400

    definicao = ConfigDefinicao.query.filter_by(chave=chave).first()
    if not definicao:
        return jsonify({'ok': False, 'error': 'definição não encontrada'}), 404

    # Validação simples por tipo
    if definicao.tipo == 'INT':
        try:
            if valor is not None and valor != '':
                int(valor)
        except Exception:
            return jsonify({'ok': False, 'error': 'valor inválido para INT'}), 400

    try:
        emp_cfg = EmpresaConfig.query.filter_by(empresa_id=empresa_id, chave=chave).first()
        if not emp_cfg:
            emp_cfg = EmpresaConfig(empresa_id=empresa_id, chave=chave, valor=valor)
            db.session.add(emp_cfg)
        else:
            emp_cfg.valor = valor
            emp_cfg.modificado_por = session.get('user_id')
        db.session.commit()
        try:
            ConfigService.clear_cache(empresa_id)
        except Exception:
            pass
        return jsonify({'ok': True, 'chave': chave, 'valor': valor})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@auth_bp.post('/empresa/api_definicoes')
@login_required
@permission_required('config.manage')
def api_create_definicao():
    data = request.get_json() or {}
    chave = (data.get('chave') or '').strip()
    descricao = data.get('descricao') or None
    valor = data.get('valor') or None
    tipo = (data.get('tipo') or 'STRING').upper()

    if not chave:
        return jsonify({'ok': False, 'error': 'Chave é obrigatória.'}), 400

    if tipo not in ('BOOLEAN', 'STRING', 'INT', 'JSON'):
        return jsonify({'ok': False, 'error': 'Tipo inválido.'}), 400

    if ConfigDefinicao.query.filter_by(chave=chave).first():
        return jsonify({'ok': False, 'error': 'Já existe uma definição com essa chave.'}), 409

    try:
        definicao = ConfigDefinicao(
            chave=chave,
            descricao=descricao,
            valor_padrao=valor,
            tipo=tipo,
            is_system=False
        )
        db.session.add(definicao)
        db.session.commit()
        return jsonify({'ok': True, 'definicao': {
            'chave': definicao.chave,
            'descricao': definicao.descricao,
            'valor_padrao': definicao.valor_padrao,
            'tipo': definicao.tipo,
            'is_system': definicao.is_system
        }})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@auth_bp.post('/empresa/api_papeis')
@login_required
@permission_required('usuario.manage')
def api_create_papel():
    empresa_id = session.get('empresa_id')
    data = request.get_json() or {}
    nome = (data.get('nome') or '').strip()
    descricao = data.get('descricao') or None
    permissoes = data.get('permissoes') or []

    if not nome:
        return jsonify({'ok': False, 'error': 'Nome é obrigatório.'}), 400

    if Papel.query.filter_by(empresa_id=empresa_id, nome=nome).first():
        return jsonify({'ok': False, 'error': 'Já existe um papel com esse nome.'}), 409

    try:
        papel = Papel(empresa_id=empresa_id, nome=nome, descricao=descricao, ativo=True, is_system=False)
        db.session.add(papel)
        db.session.flush()

        if permissoes:
            perms = Permissao.query.filter(
                Permissao.chave.in_(permissoes),
                or_(Permissao.empresa_id == empresa_id, Permissao.empresa_id.is_(None))
            ).all()
            for perm in perms:
                db.session.add(PapelPermissao(
                    empresa_id=empresa_id,
                    papel_id=papel.id,
                    permissao_id=perm.id,
                    ativo=True
                ))

        db.session.commit()
        return jsonify({'ok': True, 'papel': {
            'id': papel.id,
            'nome': papel.nome,
            'descricao': papel.descricao,
            'ativo': papel.ativo
        }})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@auth_bp.post('/empresa/api_workflows')
@login_required
@permission_required('workflow.manage')
def api_create_workflow():
    empresa_id = session.get('empresa_id')
    data = request.get_json() or {}
    nome = (data.get('nome') or '').strip()
    descricao = data.get('descricao') or None
    obra_id = data.get('obra_id')
    etapas = data.get('etapas') or []

    if not nome:
        return jsonify({'ok': False, 'error': 'Nome é obrigatório.'}), 400

    if obra_id:
        try:
            obra_id = int(obra_id)
        except Exception:
            return jsonify({'ok': False, 'error': 'Obra inválida.'}), 400

    existing = WorkflowDefinicao.query.filter_by(empresa_id=empresa_id, obra_id=obra_id, nome=nome).first()
    if existing:
        return jsonify({'ok': False, 'error': 'Já existe workflow com esse nome para esta obra.'}), 409

    try:
        workflow = WorkflowDefinicao(
            empresa_id=empresa_id,
            obra_id=obra_id,
            nome=nome,
            descricao=descricao,
            aprovacao_paralela=False,
            rejeicao_cancela_fluxo=True,
            ativo=True,
            criado_por=(session.get('user_id') if not current_app.config.get('TESTING') else None)
        )
        db.session.add(workflow)
        db.session.flush()

        nivel = 1
        for etapa in etapas:
            nome_etapa = (etapa.get('nome') or '').strip()
            if not nome_etapa:
                continue
            db.session.add(WorkflowEtapa(
                empresa_id=empresa_id,
                workflow_id=workflow.id,
                nivel=nivel,
                nome=nome_etapa,
                ativo=True,
                criado_por=(session.get('user_id') if not current_app.config.get('TESTING') else None)
            ))
            nivel += 1

        db.session.commit()
        return jsonify({'ok': True, 'workflow': {
            'id': workflow.id,
            'nome': workflow.nome,
            'descricao': workflow.descricao
        }})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@auth_bp.post('/empresa/api_workflow_default')
@login_required
@permission_required('workflow.manage')
def api_update_workflow_default():
    empresa_id = session.get('empresa_id')
    data = request.get_json() or {}
    codigo = (data.get('codigo') or '').strip()

    if not codigo:
        return jsonify({'ok': False, 'error': 'Código do workflow é obrigatório.'}), 400

    workflow = WorkflowDefinicao.query.filter(
        WorkflowDefinicao.empresa_id == empresa_id,
        WorkflowDefinicao.obra_id.is_(None),
        WorkflowDefinicao.ativo.is_(True),
        or_(
            WorkflowDefinicao.codigo == codigo,
            WorkflowDefinicao.nome == codigo,
        ),
    ).order_by(WorkflowDefinicao.id.asc()).first()
    if not workflow:
        return jsonify({'ok': False, 'error': 'Workflow padrão inválido para esta empresa.'}), 404

    try:
        _ensure_workflow_default_definition()
        config = EmpresaConfig.query.filter_by(empresa_id=empresa_id, chave='workflow.default').first()
        if not config:
            config = EmpresaConfig(
                empresa_id=empresa_id,
                chave='workflow.default',
                valor=workflow.codigo or workflow.nome,
            )
            db.session.add(config)
        else:
            config.valor = workflow.codigo or workflow.nome
        db.session.commit()
        try:
            ConfigService.clear_cache(empresa_id)
        except Exception:
            pass
        return jsonify({
            'ok': True,
            'codigo': workflow.codigo or workflow.nome,
            'nome': workflow.nome,
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@auth_bp.post('/empresa/api_workflows/<int:workflow_id>')
@login_required
@permission_required('workflow.manage')
def api_update_workflow_empresa(workflow_id):
    empresa_id = session.get('empresa_id')
    data = request.get_json() or {}

    workflow = WorkflowDefinicao.query.filter(
        WorkflowDefinicao.id == workflow_id,
        WorkflowDefinicao.empresa_id == empresa_id,
        WorkflowDefinicao.obra_id.is_(None),
        WorkflowDefinicao.ativo.is_(True),
    ).first()
    if not workflow:
        return jsonify({'ok': False, 'error': 'Workflow não encontrado para esta empresa.'}), 404

    etapas_payload = data.get('etapas') or []
    grupos_payload = data.get('grupos') or []
    if not etapas_payload:
        return jsonify({'ok': False, 'error': 'O workflow deve possuir ao menos uma etapa.'}), 400

    try:
        workflow.assinatura_obrigatoria = bool(data.get('assinatura_obrigatoria'))
        workflow.aprovacao_paralela = bool(data.get('aprovacao_paralela'))
        workflow.tipo_fluxo = (data.get('tipo_fluxo') or workflow.tipo_fluxo or 'CONFIGURAVEL').strip().upper()
        workflow.modificado_por = session.get('user_id') if not current_app.config.get('TESTING') else None
        is_simple = workflow.tipo_fluxo == 'SIMPLES'

        etapas_existentes = (
            WorkflowEtapa.query
            .filter_by(workflow_id=workflow.id)
            .order_by(WorkflowEtapa.id.asc())
            .all()
        )
        grupos_existentes = (
            WorkflowGrupo.query
            .filter_by(workflow_id=workflow.id)
            .order_by(WorkflowGrupo.id.asc())
            .all()
        )

        for idx, etapa_existente in enumerate(etapas_existentes, start=1):
            etapa_existente.nivel = 1000 + idx
            etapa_existente.ordem = 1000 + idx

        for idx, grupo_existente in enumerate(grupos_existentes, start=1):
            grupo_existente.ordem = 100000 + idx

        db.session.flush()

        if not grupos_payload:
            grupos_derivados = []
            grupos_vistos = set()
            for index, etapa_payload in enumerate(etapas_payload, start=1):
                raw_group = etapa_payload.get('workflow_group') or etapa_payload.get('grupo_paralelo') or index
                group_key = '1' if is_simple else str(raw_group)
                if group_key in grupos_vistos:
                    continue
                grupos_vistos.add(group_key)
                grupos_derivados.append({
                    'key': group_key,
                    'nome': 'Etapa 1' if is_simple else f'Grupo {len(grupos_derivados) + 1}',
                    'ordem': len(grupos_derivados) + 1,
                    'regra_aprovacao': etapa_payload.get('regra_aprovacao') or etapa_payload.get('regra_etapa') or data.get('regra_etapa'),
                })
            grupos_payload = grupos_derivados

        grupos_por_chave = {}
        for group_index, grupo_payload in enumerate(grupos_payload, start=1):
            group_key = str(grupo_payload.get('key') or grupo_payload.get('workflow_group') or grupo_payload.get('grupo_paralelo') or group_index)
            regra_aprovacao = _normalizar_regra_aprovacao_grupo(
                grupo_payload.get('regra_aprovacao') or grupo_payload.get('regra_etapa') or data.get('regra_etapa')
            )
            grupo = grupos_existentes[group_index - 1] if group_index - 1 < len(grupos_existentes) else WorkflowGrupo(
                empresa_id=empresa_id,
                workflow_id=workflow.id,
                criado_por=session.get('user_id') if not current_app.config.get('TESTING') else None,
            )
            if grupo.id is None:
                db.session.add(grupo)

            grupo.nome = (grupo_payload.get('nome') or '').strip() or ('Etapa 1' if is_simple else f'Grupo {group_index}')
            grupo.ordem = group_index
            grupo.regra_aprovacao = regra_aprovacao
            grupo.ativo = True
            grupo.modificado_por = session.get('user_id') if not current_app.config.get('TESTING') else None
            grupos_por_chave[group_key] = grupo

        for grupo_sobrando in grupos_existentes[len(grupos_payload):]:
            grupo_sobrando.ativo = False
            grupo_sobrando.modificado_por = session.get('user_id') if not current_app.config.get('TESTING') else None

        db.session.flush()

        for index, etapa_payload in enumerate(etapas_payload, start=1):
            tipo_aprovador = (etapa_payload.get('tipo_aprovador') or 'PAPEL').strip().upper()
            if tipo_aprovador not in {'USUARIO', 'PAPEL'}:
                tipo_aprovador = 'PAPEL'

            nome_etapa = (etapa_payload.get('nome') or '').strip() or f'Etapa {index}'
            papel_id = etapa_payload.get('papel_id') if tipo_aprovador == 'PAPEL' else None
            usuario_aprovador_id = etapa_payload.get('usuario_aprovador_id') if tipo_aprovador == 'USUARIO' else None
            grupo_paralelo = etapa_payload.get('grupo_paralelo')
            group_key = '1' if is_simple else str(etapa_payload.get('workflow_group') or grupo_paralelo or index)
            grupo = grupos_por_chave.get(group_key)

            if tipo_aprovador == 'PAPEL' and not papel_id:
                return jsonify({'ok': False, 'error': f'Selecione o papel da etapa {index}.'}), 400
            if tipo_aprovador == 'USUARIO' and not usuario_aprovador_id:
                return jsonify({'ok': False, 'error': f'Selecione o usuário da etapa {index}.'}), 400

            etapa = etapas_existentes[index - 1] if index - 1 < len(etapas_existentes) else WorkflowEtapa(
                empresa_id=empresa_id,
                workflow_id=workflow.id,
                criado_por=session.get('user_id') if not current_app.config.get('TESTING') else None,
            )
            if etapa.id is None:
                db.session.add(etapa)

            etapa.nivel = index
            etapa.ordem = index
            etapa.nome = nome_etapa
            etapa.tipo_aprovador = tipo_aprovador
            etapa.papel_id = int(papel_id) if papel_id else None
            etapa.usuario_aprovador_id = int(usuario_aprovador_id) if usuario_aprovador_id else None
            etapa.grupo_id = grupo.id if grupo else None
            etapa.grupo_paralelo = int(grupo_paralelo) if grupo_paralelo not in (None, '', 0, '0') else None
            etapa.obrigatorio = True
            etapa.obrigatoria = True
            etapa.assinatura_obrigatoria = workflow.assinatura_obrigatoria
            etapa.ativo = True
            etapa.modificado_por = session.get('user_id') if not current_app.config.get('TESTING') else None

        for etapa_sobrando in etapas_existentes[len(etapas_payload):]:
            etapa_sobrando.ativo = False
            etapa_sobrando.modificado_por = session.get('user_id') if not current_app.config.get('TESTING') else None

        db.session.commit()
        return jsonify({'ok': True, 'workflow_id': workflow.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

#######################################################################################################
####################################################################################################### PDF
#######################################################################################################
