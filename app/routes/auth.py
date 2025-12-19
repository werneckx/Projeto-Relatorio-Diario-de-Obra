import os
from flask import Blueprint, abort, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import check_password_hash
from app import db # Importar 'db' para uso no filtro (db.or_)
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import usuario
from app.models.obra import Frente_Trabalho, Obra
from app.models.rdo import RDO
from app.utils.rdo_pdf import regenerar_pdf_rdo
from sqlalchemy import func, or_
from datetime import date, datetime, timedelta
from functools import wraps # Mover a importação para o topo para melhor prática
from sqlalchemy.orm import aliased
from flask import request, jsonify
from app import db
from app.models.obra import Frente_Trabalho

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Página Inicial do Blueprint (Redirecionamento)
@auth_bp.get("/")
def index():
    if "user_id" in session:
        return redirect(url_for("auth.inicio"))
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Login e Logout
#######################################################################################################

# Decorator: login_required
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            # Melhoria: usa flash message para indicar a necessidade de login
            flash("Você precisa estar logado para acessar esta página.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


# Tela de Login (GET)
@auth_bp.get("/login")
def login():
    return render_template("login.html")


# Tela de Login (POST)
@auth_bp.post("/login")
def login_post():
    email = request.form.get("email")
    senha = request.form.get("senha")

    # Importar Usuario aqui, apenas onde é usado na rota
    from app.models.usuario import Usuario

    # 1. Adicionar o filtro 'ativo=1' (ou outro campo/valor que defina o status ativo)
    # Supondo que 'ativo' é um campo booleano (1 para Ativo, 0 para Inativo)
    user = Usuario.query.filter_by(email=email, status=1).first()

    # Se 'ativo' for o nome do campo de status:
    if not user or not check_password_hash(user.senha, senha):
        # O usuário não existe, a senha está incorreta OU o status não é ativo (ativo != 1)
        flash("E-mail, senha ou status de usuário inválido.", "error")
        return redirect(url_for("auth.login"))

    # Se a lógica for não filtrar no banco, mas checar o status 'ativo' depois:
    # user = Usuario.query.filter_by(email=email).first()
    # if not user or not check_password_hash(user.senha, senha) or user.ativo != 1:
    #     flash("E-mail, senha ou status de usuário inválido.", "error")
    #     return redirect(url_for("auth.login"))
    
    session["user_id"] = user.id
    session["user_name"] = user.nome
    session["user_email"] = user.email
    session["user_role"] = user.papel

    return redirect(url_for("auth.inicio"))

# Logout
@auth_bp.get("/logout")
def logout():
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Inicio
#######################################################################################################

# Página inicio
@auth_bp.get("/inicio")
@login_required
def inicio():
    return render_template("inicio.html")

# Faz o download do PDF
@auth_bp.get("/rdo/<int:rdo_id>/download")
@login_required
def download_rdo_pdf(rdo_id):
    # 'regenerar_pdf_rdo' é uma função de utilidade, mantida fora da rota
    pdf_path, pdf_filename = regenerar_pdf_rdo(rdo_id)
    return send_file(pdf_path, as_attachment=True, download_name=pdf_filename)


import json
from flask import make_response

# ... (Mantenha seus imports e decoradores existentes)

# Rota Gerar RDO (POST) - Processa Criação e Edição
@auth_bp.post("/gerar-rdo")
@login_required
def gerar_rdo():
    from app.models.rdo import RDO
    from app.models.obra import Obra
    
    # Função auxiliar interna para segurança de tipos
    def _safe_get_int(val):
        try: return int(val)
        except: return None

    rdo_id = request.form.get("id")

    if rdo_id:
        # LÓGICA DE EDIÇÃO
        # Nota: Certifique-se de que a função editar_item esteja acessível ou implementada
        # Para este escopo, chamamos a regeneração após salvar os dados via form
        try:
            regenerar_pdf_rdo(_safe_get_int(rdo_id))
            flash('RDO editado e PDF atualizado com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro ao regenerar o PDF: {e}', 'danger')
            return redirect(url_for('auth.visualizar_rdo', rdo_id=rdo_id))
    else:
        # LÓGICA DE CRIAÇÃO
        id_obra = _safe_get_int(request.form.get("id_obra"))
        obra_obj = Obra.query.get(id_obra)
        
        if not obra_obj:
            flash('Obra inválida selecionada.', 'danger')
            return redirect(url_for('auth.lista_rdo'))

        num_rdos_existentes = RDO.query.filter_by(id_obra=id_obra).count()

        # Monta a lista de mão de obra a partir do formulário
        funcoes = request.form.getlist("funcao[]")
        quantidades = request.form.getlist("quantidade[]")
        frentes = request.form.getlist("frente_trabalho[]")
        tempos = request.form.getlist("tempo_frente[]")
        mao_de_obra_data = []
        
        for i in range(max(1, len(funcoes))):
            f = funcoes[i] if i < len(funcoes) else ''
            q = quantidades[i] if i < len(quantidades) else ''
            fr = frentes[i] if i < len(frentes) else ''
            t = tempos[i] if i < len(tempos) else ''
            if f and (q or fr or t):
                mao_de_obra_data.append({
                    "funcao": f, "quantidade": q,
                    "frente_trabalho": fr, "tempo_frente": t
                })

        novo_rdo = RDO(
            id_obra=id_obra,
            id_usuario=session.get("user_id"), # Usando session conforme seu padrão
            climas_manha=_safe_get_int(request.form.get("climas_manha")),
            climas_tarde=_safe_get_int(request.form.get("climas_tarde")),
            mao_obra=json.dumps(mao_de_obra_data),
            atividades=request.form.get("atividades"),
            data=datetime.now(),
            id_sequencial=num_rdos_existentes + 1,
            status="Pendente", # Ajustado para string simples
            fotos_json='[]',
            pdf_filename=None,
            criador = session.get("user_name") # Usando session conforme seu padrão
        )
        
        db.session.add(novo_rdo)
        db.session.commit()
        rdo_id = novo_rdo.id

        # Regenera o PDF
        try:
            regenerar_pdf_rdo(rdo_id)
            flash('Novo RDO criado e PDF gerado com sucesso!', 'success')
        except Exception as e:
            flash(f'RDO criado, mas houve erro no PDF: {e}', 'danger')

    return redirect(url_for('auth.visualizar_rdo', rdo_id=rdo_id))


#######################################################################################################
####################################################################################################### RDO
#######################################################################################################

# Criar RDO (redireciona)

@auth_bp.get("/criar-rdo")
@login_required
def criar_rdo():
    from app.models.obra import Obra 
    from app.models.clima import Clima 
    from app.models.usuario import Usuario
    
    item = None
    obra = Obra.query.all()
    usuario = Usuario.query.all()
    clima = Clima.query.all()
    view_mode = False
    
    return render_template("form_rdo.html", item=item, clima=clima, obras=obra, usuarios=usuario, view_mode=view_mode)

# Visualizar RDO (redireciona)

@auth_bp.get("/visualizar-rdo/<int:rdo_id>")
@login_required
def visualizar_rdo(rdo_id):
    from app.models.rdo import RDO
    from app.models.obra import Obra
    from app.models.clima import Clima
    from app.models.usuario import Usuario

    item = RDO.query.get_or_404(rdo_id)

    return render_template(
        "form_rdo.html",
        item=item,
        view_mode=True,
        obras=Obra.query.all(),
        clima=Clima.query.all(),
        usuarios=Usuario.query.all()
    )

# Editar RDO

@auth_bp.get("/editar-rdo/<int:rdo_id>")
@login_required
def editar_rdo(rdo_id):
    from app.models.rdo import RDO
    from app.models.obra import Obra
    from app.models.clima import Clima
    from app.models.usuario import Usuario

    item = RDO.query.get_or_404(rdo_id)

    return render_template(
        "form_rdo.html",
        item=item,
        view_mode=False,
        obras=Obra.query.all(),
        clima=Clima.query.all(),
        usuarios=Usuario.query.all()
    )

# Lista RDO (placeholder)

@auth_bp.get("/lista-rdo")
@login_required
def lista_rdo():
    from app.models.rdo import RDO
    from app.models.usuario import Usuario  # Importar o modelo para acessar as permissões

    current_user_id = session.get("user_id")
    
    # 1. Buscar o objeto do usuário completo para ter acesso ao relacionamento obras_permitidas
    user = Usuario.query.get(current_user_id)

    if user:
        # 2. Extrair os IDs de todas as obras que o usuário tem permissão
        # 'obras_permitidas' foi definido no seu modelo Usuario
        ids_obras_permitidas = [obra.id for obra in user.obras_permitidas]

        # 3. Filtrar os RDOs: onde a id_obra do RDO está dentro da lista de permitidas
        rdos = RDO.query.filter(RDO.id_obra.in_(ids_obras_permitidas)).order_by(RDO.data.desc()).all()
    else:
        rdos = []

    return render_template("list_rdo.html", rdos=rdos)

#######################################################################################################
####################################################################################################### USUARIOS
#######################################################################################################

# Rota para a lista de usuários

@auth_bp.get("/lista-usuarios")
@login_required
def lista_usuarios():
    from app.models.usuario import Usuario
    # Busca todos os usuários ordenados por ID crescente
    usuarios = Usuario.query.order_by(Usuario.id.asc()).all()

    # Coleta ids de supervisor (campo `id_supervisor` pode ser string vazio)
    sup_ids = set()
    for u in usuarios:
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_ids.add(int(str(u.id_supervisor).strip()))
        except Exception:
            continue

    # Busca os usuários que são supervisores em um único query
    sup_map = {}
    if sup_ids:
        supervisors = Usuario.query.filter(Usuario.id.in_(list(sup_ids))).all()
        sup_map = {s.id: s.nome for s in supervisors}

    # Injeta atributo dinâmico 'nome_supervisor' em cada usuário (None se admin/sem supervisor)
    for u in usuarios:
        nome_sup = None
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_id = int(str(u.id_supervisor).strip())
                nome_sup = sup_map.get(sup_id)
        except Exception:
            nome_sup = None
        setattr(u, 'nome_supervisor', nome_sup)

    # Passamos explicitamente 'opcoes' e 'categoria' para o template
    return render_template("list_usuarios.html", opcoes=usuarios, categoria="usuario")

# Abrir Formulário de Cadastro de Usuario

@auth_bp.get("/criar-usuario")
@login_required
def criar_usuario():
    # from app.models.obra import Obra # Não é necessário
    
    # ADICIONADO: Obter a hierarquia das obras
    obra_hierarchy = get_obra_hierarchy_for_user_form()
    
    # Determina o Admin padrão para uso no template
    from app.models.usuario import Usuario
    admin = Usuario.query.filter_by(papel='Admin').first()
    default_supervisor = {'id': admin.id, 'nome': admin.nome} if admin else None

    # Passamos categoria='usuario' para o template saber qual seção renderizar
    return render_template(
        "form_usuario.html", 
        categoria="usuario", 
        obra_hierarchy=obra_hierarchy,
        default_supervisor=default_supervisor
    )

# Salvar/Gerar Usuario (POST)

@auth_bp.post("/gerar-usuario")
@login_required
def gerar_usuario():
    from app.models.usuario import Usuario
    from app.models.obra import Obra
    
    categoria = request.form.get("categoria")
    user_id = request.form.get("id")
    # Todas as obras é opcional, mas vamos manter o padrão do seu código
    todas_obras = Obra.query.all()
    
    # 1. ADICIONAR: Busca a hierarquia das obras no início da função
    obra_hierarchy = get_obra_hierarchy_for_user_form()

    if categoria == "usuario":
        nome = request.form.get("nome")
        email = request.form.get("email")
        papel = request.form.get("papel")
        cpf = request.form.get("cpf") 
        senha = request.form.get("senha")
        # Captura o status do checkbox (True se marcado, False caso contrário)
        status = True if request.form.get("status") == "on" else False
        obras_ids = request.form.getlist("obras_permitidas")
        # Supervisor (pode ser vazio) - se vazio, será definido como Admin padrão
        id_supervisor_raw = request.form.get('id_supervisor')

        item_form = {'id': user_id, 'nome': nome, 'email': email, 'papel': papel, 'cpf': cpf}

        if user_id:
            user = Usuario.query.get_or_404(user_id)
            # Validação CPF duplicado (exceto o próprio)
            if Usuario.query.filter(Usuario.cpf == cpf, Usuario.id != user_id).first():
                flash("Este CPF já está cadastrado.", "danger")
                # 2. CORRIGIDO: Passa obra_hierarchy em caso de erro
                return render_template("form_usuario.html", item=item_form, todas_obras=todas_obras, obra_hierarchy=obra_hierarchy)
            
            user.nome, user.email, user.papel, user.cpf, user.status = nome, email, papel, cpf, status
            # Atualiza id_supervisor se fornecido
            try:
                user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception:
                user.id_supervisor = None
        else:
            if Usuario.query.filter_by(cpf=cpf).first():
                flash("CPF já cadastrado.", "danger")
                # 3. CORRIGIDO: Passa obra_hierarchy em caso de erro
                return render_template("form_usuario.html", item=item_form, todas_obras=todas_obras, obra_hierarchy=obra_hierarchy)

            user = Usuario(nome=nome, email=email, papel=papel, cpf=cpf, status=status)
            try:
                user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception:
                user.id_supervisor = None
            user.set_senha(senha if senha else "EnfilSA@")
            db.session.add(user)

        # MODIFICADO: Diferencia entre Admin e outros papéis
        if papel == 'Admin':
            # Admin: vincula a todas as matrizes ativas
            todas_matrizes = Obra.query.filter(Obra.id_matriz.is_(None), Obra.status == 1).all()
            user.obras_permitidas = todas_matrizes
        else:
            # Outros papéis: vincula apenas as matrizes selecionadas (não filiais específicas)
            # Extrai apenas as matrizes das IDs selecionadas
            matrizes_selecionadas = []
            for oid in obras_ids:
                obra = Obra.query.get(int(oid))
                if obra:
                    # Se for uma matriz (id_matriz é None ou 0), adiciona
                    if obra.id_matriz is None or obra.id_matriz == 0:
                        matrizes_selecionadas.append(obra)
                    # Se for uma filial, adiciona sua matriz (se não estiver duplicada)
                    elif obra.id_matriz and obra.id_matriz > 0:
                        matriz = Obra.query.get(obra.id_matriz)
                        if matriz and matriz not in matrizes_selecionadas:
                            matrizes_selecionadas.append(matriz)
            
            # Vincula apenas as matrizes (filiais serão acessadas dinamicamente)
            user.obras_permitidas = matrizes_selecionadas

        # Se id_supervisor está vazio/None, define primeiro Admin como supervisor padrão
        if not getattr(user, 'id_supervisor', None):
            try:
                admin = Usuario.query.filter_by(papel='Admin').first()
                if admin:
                    user.id_supervisor = admin.id
            except Exception:
                pass

        try:
            db.session.commit()
            flash("Usuário salvo com sucesso!", "success")
            # 4. CORRIGIDO: Passa obra_hierarchy em caso de sucesso
            return render_template("form_usuario.html", item=user, todas_obras=todas_obras, view_mode=True, obra_hierarchy=obra_hierarchy)
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
            # 5. CORRIGIDO: Passa obra_hierarchy em caso de erro de DB
            return render_template("form_usuario.html", item=item_form, todas_obras=todas_obras, obra_hierarchy=obra_hierarchy)

# Mudar Status do Usuário (POST)

@auth_bp.post("/mudar-status-usuario/<int:userId>")
@login_required
def toggle_user_status(userId):
    from app.models.usuario import Usuario
    from flask import jsonify
    
    # Busca o usuário no banco
    user = Usuario.query.get_or_404(userId)
    
    # Inverte o status booleano (Se era True vira False, se era 1 vira 0)
    user.status = not user.status 
    
    try:
        db.session.commit()
        return jsonify({"message": "Status atualizado com sucesso", "status": user.status}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro ao atualizar: {str(e)}"}), 500
    
    
# Rota de Reset de Senha corrigida

@auth_bp.post("/usuario-reset/<int:id>")
@login_required
def reset_senha_usuario(id):
    from app.models.usuario import Usuario
    user = Usuario.query.get_or_404(id)
    user.set_senha("EnfilSA@") # Senha padrão solicitada
    db.session.commit()
    return {"message": "Sucesso"}, 200

# Editar Usuário
        
@auth_bp.route("/editar-usuario/<int:id>", methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    # CORREÇÃO 1: Importar a CLASSE Usuario diretamente (se necessário no escopo)
    from app.models.usuario import Usuario 
    from app.models.obra import Obra
    
    # CORREÇÃO 2: Acessar a classe Usuario e não o módulo 'usuario'
    # user = usuario.Usuario.query.get_or_404(id) # <-- Linha anterior, que causava problemas
    user = Usuario.query.get_or_404(id)
    # todas_obras = Obra.query.all() # Não é mais necessário buscar todas as obras aqui
    
    # CORREÇÃO 3: REMOVER A LÓGICA DE HIERARQUIA MANUAL E CHAMAR O HELPER CORRETO
    # Todo o bloco de código que criava 'obra_hierarchy' manualmente deve ser removido.
    obra_hierarchy = get_obra_hierarchy_for_user_form() # <-- CHAMA A FUNÇÃO CORRETA

    return render_template(
        "form_usuario.html", 
        item=user, 
        categoria="usuario", 
        # todas_obras=todas_obras, # Não é mais estritamente necessário, mas pode ser mantido
        obra_hierarchy=obra_hierarchy # Agora passa a estrutura correta
    )
    
# Visualizar Usuário

@auth_bp.get("/visualizar-usuario/<int:id>")
def visualizar_usuario(id):
    from app.models.usuario import Usuario
    from app.models.obra import Obra
    
    user = Usuario.query.get_or_404(id)
    todas_obras = Obra.query.all()
    
    obra_hierarchy = get_obra_hierarchy_for_user_form()
    # Se a rota é '/usuario/visualizar/<id>', view_mode é True.
    # Verifica a rota da requisição para determinar o modo.
    view_mode = True
    # O item de usuário já deve ter a lista de obras, 
    # mas se o relacionamento não estiver carregado, você pode forçar aqui:
    # item.obras_permitidas # Garante que o relacionamento Many-to-Many está carregado

    # Monta a cadeia de supervisores para exibição
    supervisor_chain = get_supervisor_chain_for_user(user)

    # Se o usuário tiver id_supervisor e ainda não tiver nome_supervisor injetado,
    # tenta popular nome do supervisor imediato
    nome_supervisor = None
    if getattr(user, 'id_supervisor', None):
        try:
            sup = Usuario.query.get(int(user.id_supervisor))
            nome_supervisor = sup.nome if sup else None
        except Exception:
            nome_supervisor = None

    setattr(user, 'nome_supervisor', nome_supervisor)

    # Default supervisor (Admin) caso não exista
    default_supervisor = None
    try:
        admin = Usuario.query.filter_by(papel='Admin').first()
        if admin:
            default_supervisor = {'id': admin.id, 'nome': admin.nome}
    except Exception:
        default_supervisor = None

    return render_template("form_usuario.html", item=user, categoria="usuario", todas_obras=todas_obras, view_mode=view_mode, obra_hierarchy=obra_hierarchy, supervisor_chain=supervisor_chain, default_supervisor=default_supervisor)

# Endpoint que retorna lista de usuários para selecionar como supervisor

@auth_bp.get('/supervisores')
@login_required
def lista_supervisores():
    from app.models.usuario import Usuario
    # Retorna todos os usuários (id + nome) ordenados por nome
    users = Usuario.query.order_by(Usuario.nome.asc()).all()
    result = [{'id': u.id, 'nome': u.nome, 'papel': u.papel} for u in users]
    from flask import jsonify
    return jsonify(result)

#######################################################################################################
####################################################################################################### CLIMAS
#######################################################################################################

@auth_bp.get("/lista-climas")
@login_required
def lista_climas():
    from app.models.clima import Clima
    # Busca todos os climas
    climas = Clima.query.order_by(Clima.nome.asc()).all()
    return render_template("list_climas.html", opcoes=climas, categoria="clima")


@auth_bp.get('/criar-clima')
@login_required
def criar_clima():
    # Mostra formulário para criação
    return render_template('form_clima.html', item=None, view_mode=False)


@auth_bp.post('/gerar-clima')
@login_required
def gerar_clima():
    from app.models.clima import Clima
    clima_id = request.form.get('id')
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Nome do clima é obrigatório.', 'danger')
        if clima_id:
            return redirect(url_for('auth.editar_clima', id=clima_id))
        return redirect(url_for('auth.criar_clima'))

    if clima_id:
        clima = Clima.query.get(clima_id)
        if not clima:
            flash('Clima não encontrado.', 'danger')
            return redirect(url_for('auth.lista_climas'))
        clima.nome = nome
        db.session.add(clima)
        db.session.commit()
        flash('Clima atualizado com sucesso.', 'success')
        return redirect(url_for('auth.lista_climas'))

    novo = Clima(nome=nome)
    db.session.add(novo)
    db.session.commit()
    flash('Clima criado com sucesso.', 'success')
    return redirect(url_for('auth.lista_climas'))


@auth_bp.get('/visualizar-clima/<int:id>')
@login_required
def visualizar_clima(id):
    from app.models.clima import Clima
    clima = Clima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=True)


@auth_bp.get('/editar-clima/<int:id>')
@login_required
def editar_clima(id):
    from app.models.clima import Clima
    clima = Clima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=False)


@auth_bp.post('/excluir-clima/<int:id>')
@login_required
def excluir_clima(id):
    from app.models.clima import Clima
    clima = Clima.query.get(id)
    if not clima:
        flash('Clima não encontrado.', 'danger')
        return redirect(url_for('auth.lista_climas'))
    # TODO: verificar dependências (RDOs) antes de excluir
    db.session.delete(clima)
    db.session.commit()
    return redirect(url_for('auth.lista_climas'))

#######################################################################################################
####################################################################################################### OBRAS
#######################################################################################################

# Rota para a lista de obras

@auth_bp.get("/lista-obras")
@login_required
def lista_obras():
    from app.models.obra import Obra
    
    # 1. Cria um alias (t2) para a tabela Obra. Este alias representará a Matriz/Pai.
    Matriz = aliased(Obra)
    
    # 2. Constrói a consulta com o Self-Join (LEFT OUTER JOIN)
    # Selecionamos a Obra (t1) e o nome da Matriz (t2) com o alias 'nome_matriz'
    # db.session.query é o método padrão para consultas complexas no SQLAlchemy
    consulta = db.session.query(
        Obra,
        # Seleciona o nome da Matriz, atribuindo o nome de coluna 'nome_matriz'
        Matriz.nome.label('nome_matriz')
    ).outerjoin(
        # Condição de Junção: Obra.id_matriz (da Obra Filha) = Matriz.id (da Obra Pai)
        Matriz,
        Obra.id_matriz == Matriz.id
    ).order_by(Obra.id.asc())
    
    resultados = consulta.all()
    
    # 3. Formata os resultados para o Template Jinja
    obras_formatadas = []
    for obra_obj, nome_matriz in resultados:
        # Cria um dicionário com os atributos necessários para o template
        # Isso é mais seguro do que usar obra_obj.__dict__.copy()
        obra_dict = {
            'id': obra_obj.id,
            'nome': obra_obj.nome,
            'cnpj': obra_obj.cnpj,
            'id_matriz': obra_obj.id_matriz,
            'cidade': obra_obj.cidade,
            'estado': obra_obj.estado,
            'endereco': obra_obj.endereco,
            'numero': obra_obj.numero,
            'complemento': obra_obj.complemento, # Importante: Certifique-se que este campo existe no modelo Obra
            'bairro': obra_obj.bairro,
            'cep': obra_obj.cep,
            'status': obra_obj.status,
            # 'nome_matriz' é o resultado do JOIN, adicionado ao dicionário
            'nome_matriz': nome_matriz,
        }
        
        obras_formatadas.append(obra_dict)
    
    # ... o restante da função fica igual
    return render_template("list_obras.html", opcoes=obras_formatadas, categoria="obra")
def get_matrix_options():
    """Busca todas as Obras que são Matrizes (id_matriz é NULL ou 0)"""
    # Adiciona a importação, caso Obra ainda não esteja no escopo
    from app.models.obra import Obra
    
    # Filtra por id_matriz NULL ou 0 para ser robusto com a lógica do HTML
    return Obra.query.filter(or_(Obra.id_matriz.is_(None), Obra.id_matriz == 0)).all()
def fetch_single_obra_with_matriz_name(id_obra):
    """Busca uma única Obra por ID e injeta o nome da Matriz (se for filial)"""
    from app.models.obra import Obra # Adiciona a importação
    
    Matriz = aliased(Obra)
    query = Obra.query.outerjoin(Matriz, Obra.id_matriz == Matriz.id)
    
    # Busca a Obra e o nome da Matriz associada
    result = query.with_entities(Obra, Matriz.nome.label('nome_matriz')).filter(Obra.id == id_obra).first()
    
    if result:
        # Se for encontrado, 'result' é uma tupla onde o primeiro elemento é o objeto Obra
        item = result[0]
        # Injeta o atributo 'nome_matriz' no objeto Obra para acesso no template
        setattr(item, 'nome_matriz', result.nome_matriz)
        return item
    
    return None
def get_obra_hierarchy_for_user_form():
    """Busca todas as obras e agrupa filiais sob suas matrizes."""
    from app.models.obra import Obra
    
    # Busca todas as obras ativas
    todas_obras = Obra.query.filter(Obra.status == 1).all()
    
    hierarchy = {}
    
    # 1. Popula as Matrizes (id_matriz = None ou 0)
    for obra in todas_obras:
        if obra.id_matriz is None or obra.id_matriz == 0:
            hierarchy[obra.id] = {
                'matriz': obra,
                'filiais': []
            }

    # 2. Popula as Filiais
    for obra in todas_obras:
        if obra.id_matriz and obra.id_matriz in hierarchy:
            hierarchy[obra.id_matriz]['filiais'].append(obra)
        elif obra.id_matriz and obra.id_matriz not in hierarchy:
            # Caso raro: Filial sem Matriz ativa. Pode ser ignorado ou logado.
            pass

    return hierarchy
def get_supervisor_chain_for_user(user):
    """Retorna lista de supervisores ascendentes a partir do usuário.
    Exemplo: [ {id, nome}, {id, nome}, ... ] onde o primeiro é o supervisor imediato.
    """
    from app.models.usuario import Usuario
    chain = []
    visited = set()
    current = user
    while current and getattr(current, 'id_supervisor', None):
        try:
            sup_id = int(getattr(current, 'id_supervisor'))
        except Exception:
            break
        if sup_id in visited:
            break
        sup = Usuario.query.get(sup_id)
        if not sup:
            break
        chain.append({'id': sup.id, 'nome': sup.nome})
        visited.add(sup.id)
        current = sup

    return chain

# Rota para criar nova obra

@auth_bp.get("/criar-obra")
@login_required
def criar_obra():
    from app.models.obra import Obra
    
    # Busca apenas as obras que são Matrizes para o dropdown
    opcoes_matriz = get_matrix_options()
    
    # Passa opcoes_matriz para o template
    return render_template("form_obra.html", item=None, opcoes_matriz=opcoes_matriz)

# Rota para mudar status da obra (POST)

@auth_bp.post("/mudar-status-obras/<int:obraid>")
@login_required
def toggle_user_obras(obraid):
    from app.models.usuario import Obra
    
    # Busca o usuário no banco
    obra = Obra.query.get_or_404(obraid)
    
    # Inverte o status booleano (Se era True vira False, se era 1 vira 0)
    obra.status = not obra.status 
    
    try:
        db.session.commit()
        return {"message": "Status atualizado com sucesso"}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"Erro ao atualizar: {str(e)}"}, 500
    
# Rota para salvar obra

@auth_bp.post("/gerar-obra")
@login_required
def gerar_obra():
    from app.models.obra import Obra
    
    # 1. Obter Dados do Formulário
    id_obra = request.form.get("id", type=int)
    nome = request.form.get("nome")
    cnpj = request.form.get("cnpj")
    endereco = request.form.get("endereco")
    numero = request.form.get("numero")
    complemento = request.form.get("complemento")
    bairro = request.form.get("bairro")
    cidade = request.form.get("cidade")
    estado = request.form.get("estado")
    cep = request.form.get("cep")
    inicio_str = request.form.get("inicio")
    termino_str = request.form.get("termino")
    
    # Processa id_matriz: Se for 0 ou None, deve ser None no DB (Matriz Principal)
    id_matriz_raw = request.form.get("id_matriz", type=int)
    id_matriz = id_matriz_raw if id_matriz_raw and id_matriz_raw > 0 else None
    
    # Converte datas
    try:
        inicio = datetime.strptime(inicio_str, '%Y-%m-%d').date() if inicio_str else None
        termino = datetime.strptime(termino_str, '%Y-%m-%d').date() if termino_str else None
    except ValueError:
        flash("Formato de data inválido.", "danger")
        # Prepara o item_form para retornar ao template em caso de erro
        item_form = Obra(
            id=id_obra, nome=nome, cnpj=cnpj, id_matriz=id_matriz, endereco=endereco, 
            numero=numero, complemento=complemento, bairro=bairro, cidade=cidade, 
            estado=estado, cep=cep, inicio=inicio_str, termino=termino_str # Mantém strings para re-exibir
        )
        return render_template("form_obra.html", item=item_form, view_mode=False)


    # Converte o status do checkbox ('on' se ativo)
    status_raw = request.form.get("status")
    status = "Ativa" if status_raw == 'on' else "Inativa"

    # Prepara o item_form (para re-renderizar em caso de erro de DB)
    item_form = Obra(
        id=id_obra, nome=nome, cnpj=cnpj, id_matriz=id_matriz, endereco=endereco, 
        numero=numero, complemento=complemento, bairro=bairro, cidade=cidade, 
        estado=estado, cep=cep, inicio=inicio, termino=termino, status=status
    )
    
    # 2. Criar ou Atualizar
    if id_obra:
        # Edição
        item = Obra.query.get_or_404(id_obra)
        item.nome = nome
        item.cnpj = cnpj
        item.id_matriz = id_matriz # Novo campo
        item.endereco = endereco
        item.numero = numero
        item.complemento = complemento
        item.bairro = bairro
        item.cidade = cidade
        item.estado = estado
        item.cep = cep
        item.inicio = inicio
        item.termino = termino
        item.status = status
        acao = "atualizada"
    else:
        # Criação
        obra = Obra(
            nome=nome,
            cnpj=cnpj,
            id_matriz=id_matriz, # Novo campo
            endereco=endereco,
            numero=numero,
            complemento=complemento,
            bairro=bairro,
            cidade=cidade,
            estado=estado,
            cep=cep,
            inicio=inicio,
            termino=termino,
            status=status
        )
        db.session.add(obra)
        item_form = obra # Atualiza o item_form com a nova obra para o redirecionamento
        acao = "cadastrada"

    # 3. Commit ao Banco de Dados
    try:
        db.session.commit()
        flash(f"Obra '{nome}' {acao} com sucesso!", "success")
        # No sucesso, usa a rota de visualização para mostrar os dados salvos
        return redirect(url_for('auth.visualizar_obra', id=item_form.id)) 
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar/editar obra: {e}")
        flash("Ocorreu um erro ao salvar a obra. Tente novamente.", "danger")
        # Em caso de erro de DB, retorna ao template com os dados do formulário
        # Precisa buscar opções_matriz novamente
        opcoes_matriz = get_matrix_options()
        return render_template("form_obra.html", item=item_form, view_mode=False, opcoes_matriz=opcoes_matriz)
    
# Rota pra editar obra

@auth_bp.get("/editar-obra/<int:id>")
@login_required
def editar_obra(id):
    from app.models.usuario import Usuario
    # Usa o helper para buscar a Obra com o nome da Matriz
    item = fetch_single_obra_with_matriz_name(id)
    
    obra = Obra.query.get_or_404(id)
    # Busca todas as frentes vinculadas a essa obra
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()
    
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    
    # Busca outras obras para o select de Matriz
    opcoes_matriz = Obra.query.all()
    
    if not item:
        abort(404) # Not Found
    
    # Busca as opções de Matriz
    opcoes_matriz = get_matrix_options()
    
    # Passa as opções de matrizes e o item com nome_matriz para o template
    return render_template("form_obra.html", item=item, opcoes_matriz=opcoes_matriz, frentes=frentes, usuarios=usuarios)

# Rota para visualizar obra
@auth_bp.get("/visualizar-obra/<int:id>")
@login_required
def visualizar_obra(id):
    from app.models.obra import Obra
    from app.models.usuario import Usuario
    
    # Busca o item de Obra
    item = Obra.query.get_or_404(id) 
    item = fetch_single_obra_with_matriz_name(id)

    # Define view_mode como True para bloquear os campos no template
    view_mode = True
    if not item:
        abort(404)
        
    opcoes_matriz = get_matrix_options()
    
    frentes = Frente_Trabalho.query.filter_by(id_obra=id).all()

    usuario = Usuario.query.order_by(Usuario.nome).all()
    
    # Renderiza o template passando o item e o view_mode
    return render_template(
        "form_obra.html", 
        item=item, 
        view_mode=view_mode, 
        categoria="obra",
        opcoes_matriz=opcoes_matriz, # Importante passar isso para o <select> funcionar
        frentes=frentes,
        usuario=usuario
    )

# Rota para toggle de status da obra (usado em list_obras.html)

@auth_bp.post("/obra/toggle-status/<int:id>")
@login_required
def toggle_obra_status(id):
    from app.models.obra import Obra
    
    obra = Obra.query.get_or_404(id)
    
    # Alterna o status (Ativa <-> Inativa)
    if obra.status == 1:
        obra.status = 0
    else:
        obra.status = 1
        
    try:
        db.session.commit()
        return '', 200 # Retorna 200 OK para o JavaScript
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao alternar status da obra: {e}")
        return '', 500 # Retorna erro 500

# Rota para criar nova frente de trabalho

@auth_bp.route('/criar-frente', methods=['POST'])
@login_required
def criar_frente():
    from app.models.usuario import Usuario

    data = request.get_json()

    id_obra = data.get('id_obra')
    nome_frente = data.get('nome_frente')
    id_responsavel = data.get('id_responsavel')

    if not id_obra or not nome_frente:
        return jsonify({'success': False, 'message': 'Dados incompletos'}), 400

    try:
        usuario = None
        nome_responsavel = 'Não definido'

        if id_responsavel:
            usuario = Usuario.query.filter_by(id=id_responsavel).first()
            if usuario:
                nome_responsavel = usuario.nome

        nova_frente = Frente_Trabalho(
            id_obra=id_obra,
            nome_frente=nome_frente,
            id_responsavel=id_responsavel if usuario else None
        )

        db.session.add(nova_frente)
        db.session.commit()

        return jsonify({
            'success': True,
            'id_frente_trabalho': nova_frente.id_frente_trabalho,
            'nome_frente': nova_frente.nome_frente,
            'responsavel': nome_responsavel
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Rota para remover frente de trabalho
@auth_bp.route('/remover-frente/<int:id>', methods=['DELETE'])
def remover_frente(id):
    try:
        frente = Frente_Trabalho.query.get_or_404(id)
        db.session.delete(frente)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500