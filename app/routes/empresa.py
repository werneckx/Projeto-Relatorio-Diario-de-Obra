from app.routes.auth_common import *

#######################################################################################################
####################################################################################################### Empresa
#######################################################################################################

@auth_bp.app_context_processor
def inject_company_info():
    if current_user.is_authenticated:
        empresa = getattr(current_user, 'empresa', None)
        nome = empresa.nome if empresa else "Não definida"
        
        # Logos da empresa (fallback para o sistema)
        logo_empresa = empresa.logo_empresa if empresa and empresa.logo_empresa else 'logo/logo_sistema.png'
        icone_empresa = empresa.icone_empresa if empresa and empresa.icone_empresa else 'logo/icone_sistema.png'
        
        return dict(
            nome_empresa=nome,
            logo_empresa=logo_empresa,
            icone_empresa=icone_empresa,
            usuario_atual=current_user
        )
    return dict(nome_empresa="Não logado", logo_empresa="logo/logo_sistema.png", icone_empresa="logo/icone_sistema.png", usuario_atual=None)

@auth_bp.get("/empresa")
@login_required
@role_required([ROLE_ADMIN]) # SECURITY: Apenas Admin acessa configs da empresa
def empresa():
    empresa_db = Empresa.query.filter_by(id=session.get('empresa_id')).first()
    config_data = {
        'nome': empresa_db.nome if empresa_db else '',
        'logo_path': empresa_db.logo_empresa if empresa_db and empresa_db.logo_empresa else 'logo/logo_sistema.png',
        'icone_path': empresa_db.icone_empresa if empresa_db and empresa_db.icone_empresa else 'logo/icone_sistema.png'
    } 
    return render_template('empresa.html', config_data=config_data, view_mode=True)

@auth_bp.route('/salvar-empresa', methods=['POST'])
@login_required
@role_required([ROLE_ADMIN]) # SECURITY: Apenas Admin salva
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

#######################################################################################################
####################################################################################################### PDF
#######################################################################################################
