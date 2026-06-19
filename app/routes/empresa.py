from app.routes.auth_common import *
from datetime import datetime

from app.services.config_service import ConfigService
from app.models.configuracao import ConfigDefinicao, EmpresaConfig
from app.models.usuario import Papel, Permissao, PapelPermissao
from app.models.workflow import WorkflowDefinicao, WorkflowEtapa, WorkflowResponsavel
from app.models.obra import Obra
from app.models.usuario import Usuario


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
    if current_user.is_authenticated:
        empresa = getattr(current_user, 'empresa', None)

        # `current_user.empresa` pode estar detached/expired no contexto de render.
        # Recarrega a instância pela chave primária antes de acessar atributos.
        empresa_db = None
        if empresa is not None:
            empresa_id = getattr(empresa, "id", None)
            if empresa_id is not None:
                empresa_db = db.session.get(type(empresa), empresa_id)

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

    return dict(
        nome_empresa="Não logado",
        logo_empresa="logo/logo_sistema.png",
        icone_empresa="logo/icone_sistema.png",
        usuario_atual=None
    )

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
    workflow_responsaveis = (
        WorkflowResponsavel.query
        .filter_by(empresa_id=empresa_id, ativo=True)
        .outerjoin(Obra, Obra.id == WorkflowResponsavel.obra_id)
        .outerjoin(Papel, Papel.id == WorkflowResponsavel.papel_id)
        .outerjoin(Usuario, Usuario.id == WorkflowResponsavel.usuario_id)
        .order_by(
            WorkflowResponsavel.obra_id.isnot(None).asc(),
            Obra.nome.asc(),
            Papel.nome.asc(),
            WorkflowResponsavel.prioridade.asc(),
            WorkflowResponsavel.id.asc(),
        )
        .all()
    )
    obras = Obra.query.filter_by(empresa_id=empresa_id).order_by(Obra.nome).all()
    permissoes_disponiveis = Permissao.query.filter((Permissao.empresa_id == empresa_id) | (Permissao.empresa_id.is_(None))).order_by(Permissao.chave).all()

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
        workflows_empresa_padrao=workflows_empresa_padrao,
        workflow_default_codigo=workflow_default_codigo,
        workflow_responsaveis=workflow_responsaveis,
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


@auth_bp.post('/empresa/api_workflow_responsaveis')
@login_required
@permission_required('workflow.manage')
def api_create_workflow_responsavel():
    empresa_id = session.get('empresa_id')
    data = request.get_json() or {}

    papel_id = data.get('papel_id')
    usuario_id = data.get('usuario_id')
    obra_id = data.get('obra_id')
    prioridade = data.get('prioridade', 1)

    if not papel_id or not usuario_id:
        return jsonify({'ok': False, 'error': 'Papel e usuário são obrigatórios.'}), 400

    try:
        papel_id = int(papel_id)
        usuario_id = int(usuario_id)
        obra_id = int(obra_id) if obra_id not in (None, '', 0, '0') else None
        prioridade = int(prioridade or 1)
    except Exception:
        return jsonify({'ok': False, 'error': 'Parâmetros inválidos.'}), 400

    papel = Papel.query.filter(
        Papel.id == papel_id,
        Papel.ativo.is_(True),
        or_(Papel.empresa_id == empresa_id, Papel.empresa_id.is_(None)),
    ).first()
    if not papel:
        return jsonify({'ok': False, 'error': 'Papel inválido para esta empresa.'}), 404

    usuario = Usuario.query.filter_by(id=usuario_id, empresa_id=empresa_id, ativo=True).first()
    if not usuario:
        return jsonify({'ok': False, 'error': 'Usuário inválido para esta empresa.'}), 404

    obra = None
    if obra_id is not None:
        obra = Obra.query.filter_by(id=obra_id, empresa_id=empresa_id).first()
        if not obra:
            return jsonify({'ok': False, 'error': 'Obra inválida para esta empresa.'}), 404

    try:
        (
            WorkflowResponsavel.query
            .filter_by(empresa_id=empresa_id, obra_id=obra_id, papel_id=papel_id, ativo=True)
            .update(
                {
                    WorkflowResponsavel.ativo: False,
                    WorkflowResponsavel.modificado_por: session.get('user_id'),
                    WorkflowResponsavel.modificado_em: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )

        responsavel = WorkflowResponsavel(
            empresa_id=empresa_id,
            obra_id=obra_id,
            papel_id=papel_id,
            usuario_id=usuario_id,
            prioridade=max(prioridade, 1),
            ativo=True,
            criado_por=(session.get('user_id') if not current_app.config.get('TESTING') else None),
        )
        db.session.add(responsavel)
        db.session.commit()
        return jsonify({
            'ok': True,
            'responsavel': {
                'id': responsavel.id,
                'obra_id': responsavel.obra_id,
                'obra_nome': obra.nome if obra else None,
                'papel_id': responsavel.papel_id,
                'papel_nome': papel.nome,
                'usuario_id': responsavel.usuario_id,
                'usuario_nome': usuario.nome,
                'prioridade': responsavel.prioridade,
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


@auth_bp.post('/empresa/api_workflow_responsaveis/<int:responsavel_id>/inativar')
@login_required
@permission_required('workflow.manage')
def api_inativar_workflow_responsavel(responsavel_id):
    empresa_id = session.get('empresa_id')
    responsavel = WorkflowResponsavel.query.filter_by(
        id=responsavel_id,
        empresa_id=empresa_id,
        ativo=True,
    ).first()
    if not responsavel:
        return jsonify({'ok': False, 'error': 'Responsável não encontrado.'}), 404

    try:
        responsavel.ativo = False
        responsavel.modificado_por = session.get('user_id')
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

#######################################################################################################
####################################################################################################### PDF
#######################################################################################################
