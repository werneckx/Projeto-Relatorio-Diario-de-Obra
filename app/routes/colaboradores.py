from app.routes.auth_common import *

# --- COLABORADORES ---
@auth_bp.get("/lista-colaboradores")
@login_required
def lista_colaboradores():
    colaboradores = AuxColaboradores.query.filter_by(ativo=True).order_by(AuxColaboradores.nome.asc()).all()
    return render_template("list_colaboradores.html", opcoes=colaboradores, categoria="colaborador")

@auth_bp.get('/criar-colaborador')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_colaborador():
    return render_template('form_colaborador.html', item=None, view_mode=False)

@auth_bp.post('/gerar-colaborador')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_colaborador():
    colaborador_id = request.form.get('id')
    nome = _normalize_option_input(request.form.get('nome', ''))
    cargo = _normalize_option_input(request.form.get('cargo', ''))
    telefone = _normalize_option_input(request.form.get('telefone', ''))
    ativo = request.form.get('ativo') == '1'
    
    if not nome:
        flash('Nome do colaborador é obrigatório.', 'danger')
        return redirect(url_for('auth.lista_colaboradores'))

    if colaborador_id:
        colaborador = AuxColaboradores.query.get(colaborador_id)
        colaborador.nome = nome
        colaborador.cargo = cargo
        colaborador.telefone = telefone
        colaborador.ativo = ativo
    else:
        novo = AuxColaboradores(nome=nome, cargo=cargo, telefone=telefone, tipo_lista="Colaboradores", ativo=ativo)
        db.session.add(novo)
        
    db.session.commit()
    return redirect(url_for('auth.lista_colaboradores'))

@auth_bp.post('/excluir-colaborador/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_colaborador(id):
    colaborador = AuxColaboradores.query.get(id)
    if colaborador:
        colaborador.ativo = False
        db.session.commit()
    return redirect(url_for('auth.lista_colaboradores'))

class AuxColaboradores(db.Model):
    __tablename__ = 'aux_colaboradores'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    cargo = db.Column(db.String(100), nullable=True)
    telefone = db.Column(db.String(20), nullable=True)
    tipo_lista = db.Column(db.String(50), default="Colaboradores")
    ativo = db.Column(db.Boolean, default=True)