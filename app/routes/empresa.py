from app.routes.auth_common import *
from collections import defaultdict
from datetime import datetime

from app.services.config_service import ConfigService
from app.models.configuracao import ConfigDefinicao, EmpresaConfig
from app.models.usuario import Papel, Permissao, PapelPermissao
from app.models.workflow import WorkflowDefinicao, WorkflowEtapa, WorkflowExecucao, WorkflowExecucaoEtapa
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

@auth_bp.get("/empresa")
@login_required
@permission_required('empresa.manage')
def empresa():
    empresa_id = session.get('empresa_id')
    empresa_db = Empresa.query.filter_by(id=empresa_id).first()
    config_data = {
        'nome': empresa_db.nome if empresa_db else '',
        'logo_path': empresa_db.logo_empresa if empresa_db and empresa_db.logo_empresa else 'logo/logo_sistema.png',
        'icone_path': empresa_db.icone_empresa if empresa_db and empresa_db.icone_empresa else 'logo/icone_sistema.png'
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
        for etapa in workflow_etapas_map.get(workflow_default.id, []):
            workflow_default_etapas_resumo.append({
                'nivel': etapa.nivel,
                'nome': etapa.nome,
                'tipo': etapa.tipo_aprovador or 'USUARIO',
                'papel': etapa.papel.nome if etapa.papel else (etapa.usuario_aprovador.nome if etapa.usuario_aprovador else etapa.nome),
                'tempo_medio': medias_etapa.get(etapa.id, 'Sem histórico'),
            })

    obras_modal_payload = []
    for resumo in obras_workflow_resumo:
        obra = resumo['obra']
        workflow_resolvido = resumo['workflow']
        etapas_resolvidas = workflow_etapas_map.get(workflow_resolvido.id, []) if workflow_resolvido else []
        execucoes_ativas_obra = [
            execucao for execucao in workflow_execucoes_all
            if execucao.obra_id == obra.id and execucao.status in {'PENDENTE', 'EM_ANDAMENTO', 'REABERTO'}
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

        obras_modal_payload.append({
            'obra_id': obra.id,
            'obra_nome': obra.nome,
            'workflow_nome': workflow_resolvido.nome if workflow_resolvido else 'Sem workflow',
            'workflow_origem': 'Herdado da Empresa' if resumo['herda_empresa'] else ('Workflow Próprio da Obra' if resumo['workflow_proprio'] else 'Sem definição'),
            'workflow_origem_tipo': 'empresa' if resumo['herda_empresa'] else ('obra' if resumo['workflow_proprio'] else 'indefinido'),
            'responsavel': obra.usuario_responsavel.nome if obra.usuario_responsavel else 'Não definido',
            'execucoes_ativas': len(execucoes_ativas_obra),
            'matriz_total': len(matriz_obra),
            'status': 'Com pendências' if execucoes_ativas_obra else 'Sem pendências',
            'matriz': matriz_obra,
            'workflow_etapas': [
                {
                    'nivel': etapa.nivel,
                    'nome': etapa.nome,
                    'tipo': etapa.tipo_aprovador or 'USUARIO',
                    'papel': etapa.papel.nome if etapa.papel else etapa.nome,
                    'tempo_medio': medias_etapa.get(etapa.id, 'Sem histórico'),
                }
                for etapa in etapas_resolvidas
            ],
        })

    # Permissão de edição efetiva (por segurança, permission_required já garante acesso)
    user = get_current_user()
    can_edit = False
    if user:
        try:
            can_edit = user.tem_permissao('empresa.manage')
        except Exception:
            can_edit = False

    return render_template(
        'empresa/empresa.html',
        config_data=config_data,
        view_mode=True,
        config_map=mapa,
        definicoes=definicoes,
        papeis_globais=papeis_globais,
        papeis_empresa=papeis_empresa,
        papeis_workflow=papeis_workflow,
        usuarios_empresa=usuarios_empresa,
        workflows=workflows,
        workflows_resumo=workflows_resumo,
        workflows_empresa_padrao=workflows_empresa_padrao,
        workflow_default_codigo=workflow_default_codigo,
        workflow_default=workflow_default,
        workflow_default_etapas=workflow_etapas_map.get(workflow_default.id, []) if workflow_default else [],
        workflow_default_etapas_resumo=workflow_default_etapas_resumo,
        workflow_execucoes=workflow_execucoes,
        workflow_status_counts=workflow_status_counts,
        workflow_metricas=workflow_metricas,
        workflow_matriz_responsabilidades=workflow_matriz_responsabilidades,
        obras_workflow_resumo=obras_workflow_resumo,
        obras_modal_payload=obras_modal_payload,
        obras=obras,
        permissoes_disponiveis=permissoes_disponiveis,
        can_edit=can_edit
    )

@auth_bp.route('/salvar-empresa', methods=['POST'])
@login_required
@permission_required('empresa.manage')
def salvar_empresa():
    nome_empresa = request.form.get('nome_empresa')
    logo_file = request.files.get('logo_empresa')
    icone_file = request.files.get('icone_empresa')
    empresa_id = session.get('empresa_id')

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

    return redirect(url_for('auth.empresa'))


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

#######################################################################################################
####################################################################################################### PDF
#######################################################################################################
