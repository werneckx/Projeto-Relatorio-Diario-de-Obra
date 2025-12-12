from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import check_password_hash
from app import db # Importar 'db' para uso no filtro (db.or_)
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import usuario
from app.models.obra import Obra
from app.utils.rdo_pdf import regenerar_pdf_rdo
from sqlalchemy import func
from datetime import date, datetime, timedelta
from functools import wraps # Mover a importação para o topo para melhor prática

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


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

    return redirect(url_for("auth.home"))

# Página Home
@auth_bp.get("/home")
@login_required
def home():
    return render_template("inicio.html")


# Logout
@auth_bp.get("/logout")
def logout():
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for("auth.login"))


# Página Inicial do Blueprint (Redirecionamento)
@auth_bp.get("/")
def index():
    if "user_id" in session:
        return redirect(url_for("auth.home"))
    return redirect(url_for("auth.login"))


# Lista RDO (placeholder)
# No arquivo auth.py
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

        # 3. Filtrar os RDOs: onde a obra_id do RDO está dentro da lista de permitidas
        rdos = RDO.query.filter(RDO.obra_id.in_(ids_obras_permitidas)).order_by(RDO.data.desc()).all()
    else:
        rdos = []

    return render_template("list_rdo.html", rdos=rdos)

# Faz o download do PDF
@auth_bp.get("/rdo/<int:rdo_id>/download")
@login_required
def download_rdo_pdf(rdo_id):
    # 'regenerar_pdf_rdo' é uma função de utilidade, mantida fora da rota
    pdf_path, pdf_filename = regenerar_pdf_rdo(rdo_id)
    return send_file(pdf_path, as_attachment=True, download_name=pdf_filename)

# Faz o Editar do RDO
@auth_bp.get("/rdo/<int:rdo_id>/editar")
@login_required
def editar_rdo(rdo_id):
    # Sugestão de Melhoria: Esta rota deve buscar os dados do RDO
    # rdo = RDO.query.get_or_404(rdo_id)
    return render_template("form_rdo.html", rdo_id=rdo_id)
# Faz o Visualizar do RDO
@auth_bp.get("/rdo/<int:rdo_id>")
@login_required
def visualizar_rdo(rdo_id):
    # Sugestão de Melhoria: Esta rota deve buscar os dados do RDO
    # rdo = RDO.query.get_or_404(rdo_id)
    return render_template("form_rdo.html", rdo_id=rdo_id)

# Criar RDO (redireciona)
@auth_bp.get("/novo-rdo")
@login_required
def adicionar_rdo():
    return render_template("form_rdo.html")


# LISTA GENÉRICA /cadastro/<categoria>
@auth_bp.route("/cadastro/<categoria>")
@login_required
def cadastro_list(categoria):

    # CORREÇÃO: Importar Modelos SOMENTE AQUI, onde eles são usados.
    # Isso evita que a importação do 'Clima' (e a possível query no seu modelo)
    # ocorra quando o Blueprint é registrado no create_app.
    from app.models.usuario import Usuario
    from app.models.obra import Obra
    from app.models.clima import Clima 

    search = request.args.get("search", "").strip()

    # Mapeia nome de categoria -> classe/model
    model_map = {
        "obra": Obra,
        "usuario": Usuario,
        "clima": Clima,
    }

    Model = model_map.get(categoria)

    if Model is None:
        flash("Categoria inválida.", "danger")
        return redirect(url_for("auth.home"))

    # Query base
    q = Model.query

    # Filtro de busca
    if search:
        if categoria == "usuario":
            q = q.filter(
                db.or_(
                    Usuario.nome.ilike(f"%{search}%"),
                    Usuario.email.ilike(f"%{search}%"),
                    Usuario.role.ilike(f"%{search}%"),
                )
            )
        else:
            # Para obras e clima assume que possuem campo nome
            # Nota: É crucial que a classe Clima tenha um atributo 'nome'
            # Se 'Clima' usa 'descricao' ou outro campo, isso quebrará aqui.
            try:
                q = q.filter(Model.nome.ilike(f"%{search}%"))
            except AttributeError:
                flash(f"Modelo {Model.__name__} não possui atributo 'nome' para busca.", "error")
                return redirect(url_for("auth.home"))


    # Ordenação por ID crescente
    opcoes = q.order_by(Model.id.asc()).all()

    # Sugestão de Melhoria: Você precisa passar 'opcoes', 'categoria' e 'search'
    # para o template list_obras.html para que ele possa renderizar a lista.
    # return render_template("list_obras.html", itens=opcoes, categoria=categoria, search=search)
    return render_template("list_obras.html")

import json
from flask import make_response

# ... (Mantenha seus imports e decoradores existentes)

# Rota Gerar RDO (POST) - Processa Criação e Edição
@auth_bp.post("/gerar")
@login_required
def gerar():
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
        obra_id = _safe_get_int(request.form.get("obra_id"))
        obra_obj = Obra.query.get(obra_id)
        
        if not obra_obj:
            flash('Obra inválida selecionada.', 'danger')
            return redirect(url_for('auth.lista_rdo'))

        num_rdos_existentes = RDO.query.filter_by(obra_id=obra_id).count()

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
            obra_id=obra_id,
            usuario_id=session.get("user_id"), # Usando session conforme seu padrão
            climas_manha=_safe_get_int(request.form.get("climas_manha")),
            climas_tarde=_safe_get_int(request.form.get("climas_tarde")),
            mao_obra=json.dumps(mao_de_obra_data),
            atividades=request.form.get("atividades"),
            data=datetime.now(),
            numero_sequencial=num_rdos_existentes + 1,
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

# Rota de Sucesso (Callback)
@auth_bp.get("/rdo_success")
@login_required
def rdo_success():
    rdo_data_json = request.cookies.get('rdo_success_data')
    if rdo_data_json:
        response = make_response(redirect(url_for('auth.lista_rdo')))
        response.set_cookie('rdo_success_data', '', expires=0)
        flash(rdo_data_json, 'success')
        return response
    return redirect(url_for('auth.lista_rdo'))

# No seu ficheiro auth.py

# Rota para a lista de usuários
@auth_bp.get("/lista-usuarios")
@login_required
def lista_usuarios():
    from app.models.usuario import Usuario
    # Busca todos os usuários ordenados por ID
    usuarios = Usuario.query.order_by(Usuario.id.asc()).all()
    # Passamos explicitamente 'opcoes' e 'categoria' para o template
    return render_template("list_usuarios.html", opcoes=usuarios, categoria="usuario")

# Abrir Formulário de Cadastro de Usuario
@auth_bp.get("/criar-usuario")
@login_required
def criar_usuario():
    from app.models.obra import Obra
    # Busca todas as obras cadastradas para exibir nas permissões do formulário
    todas_obras = Obra.query.all()
    
    # Passamos categoria='usuario' para o template saber qual seção renderizar
    return render_template("form_usuario.html", categoria="usuario", todas_obras=todas_obras)

# app/routes/auth.py

@auth_bp.post("/gerar-usuario")
@login_required
def gerar_usuario():
    from app.models.usuario import Usuario
    from app.models.obra import Obra
    
    categoria = request.form.get("categoria")
    user_id = request.form.get("id")
    todas_obras = Obra.query.all()

    if categoria == "usuario":
        nome = request.form.get("nome")
        email = request.form.get("email")
        papel = request.form.get("papel")
        cpf = request.form.get("cpf") 
        senha = request.form.get("senha")
        # Captura o status do checkbox (True se marcado, False caso contrário)
        status = True if request.form.get("status") == "on" else False
        obras_ids = request.form.getlist("obras_permitidas")

        item_form = {'id': user_id, 'nome': nome, 'email': email, 'papel': papel, 'cpf': cpf}

        if user_id:
            user = Usuario.query.get_or_404(user_id)
            # Validação CPF duplicado (exceto o próprio)
            if Usuario.query.filter(Usuario.cpf == cpf, Usuario.id != user_id).first():
                flash("Este CPF já está cadastrado.", "danger")
                return render_template("form_usuario.html", item=item_form, todas_obras=todas_obras)
            
            user.nome, user.email, user.papel, user.cpf, user.status = nome, email, papel, cpf, status
        else:
            if Usuario.query.filter_by(cpf=cpf).first():
                flash("CPF já cadastrado.", "danger")
                return render_template("form_usuario.html", item=item_form, todas_obras=todas_obras)

            user = Usuario(nome=nome, email=email, papel=papel, cpf=cpf, status=status)
            user.set_senha(senha if senha else "EnfilSA@")
            db.session.add(user)

        user.obras_permitidas = [Obra.query.get(int(oid)) for oid in obras_ids if Obra.query.get(int(oid))]

        try:
            db.session.commit()
            flash("Usuário salvo com sucesso!", "success")
            return render_template("form_usuario.html", item=user, todas_obras=todas_obras, view_mode=True)
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
            return render_template("form_usuario.html", item=item_form, todas_obras=todas_obras)

# No seu arquivo auth.py

@auth_bp.post("/mudar-status-usuario/<int:userId>")
@login_required
def toggle_user_status(userId):
    from app.models.usuario import Usuario
    
    # Busca o usuário no banco
    user = Usuario.query.get_or_404(userId)
    
    # Inverte o status booleano (Se era True vira False, se era 1 vira 0)
    user.status = not user.status 
    
    try:
        db.session.commit()
        return {"message": "Status atualizado com sucesso"}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"Erro ao atualizar: {str(e)}"}, 500
    
# Rota de Reset de Senha corrigida
@auth_bp.post("/usuario-reset/<int:id>")
@login_required
def reset_senha_usuario(id):
    from app.models.usuario import Usuario
    user = Usuario.query.get_or_404(id)
    user.set_senha("EnfilSA@") # Senha padrão solicitada
    db.session.commit()
    return {"message": "Sucesso"}, 200
        
@auth_bp.get("/editar-usuario/<int:id>")
@login_required
def editar_usuario(id):
    from app.models.usuario import Usuario
    from app.models.obra import Obra
    
    user = Usuario.query.get_or_404(id)
    todas_obras = Obra.query.all()
    
    return render_template("form_usuario.html", item=user, categoria="usuario", todas_obras=todas_obras)

@auth_bp.get("/visualizar-usuario/<int:id>")
def visualizar_usuario(id):
    from app.models.usuario import Usuario
    from app.models.obra import Obra
    
    user = Usuario.query.get_or_404(id)
    todas_obras = Obra.query.all()
    
    # Se a rota é '/usuario/visualizar/<id>', view_mode é True.
    # Verifica a rota da requisição para determinar o modo.
    view_mode = True
    # O item de usuário já deve ter a lista de obras, 
    # mas se o relacionamento não estiver carregado, você pode forçar aqui:
    # item.obras_permitidas # Garante que o relacionamento Many-to-Many está carregado

    return render_template("form_usuario.html", item=user, categoria="usuario", todas_obras=todas_obras, view_mode=view_mode)

# Rota para a lista de climas
@auth_bp.get("/lista-climas")
@login_required
def lista_climas():
    from app.models.clima import Clima
    # Busca todos os climas
    climas = Clima.query.order_by(Clima.id.asc()).all()
    return render_template("list_climas.html", opcoes=climas, categoria="clima")

# Rota para a lista de obras
@auth_bp.get("/lista-obras")
@login_required
def lista_obras():
    from app.models.obra import Obra
    # Busca todas as obras
    obras = Obra.query.order_by(Obra.id.asc()).all()
    return render_template("list_obras.html", opcoes=obras, categoria="obra")

# Rota pra criar obra

@auth_bp.get("/criar-obra")
@login_required
def criar_obra():
    
    # Passamos categoria='usuario' para o template saber qual seção renderizar
    return render_template("form_obra.html", categoria="usuario")


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
    
    
# Rota para gerar obra 
# Rota para Criar/Editar Obra (POST)
@auth_bp.post("/gerar-obra")
@login_required
def gerar_obra(): 
    form_data = request.form
    obra_id = form_data.get("id")

    # Cria um dicionário com os dados do formulário (strings) para retorno em caso de erro
    item_form = {
        'id': obra_id,
        'nome': form_data.get("nome", "").strip(),
        # CNPJ e CEP limpos, mas salvos como string (o modelo aceita)
        'cnpj': form_data.get("cnpj", "").replace('.', '').replace('-', '').replace('/', '').strip(),
        'cep': form_data.get("cep", "").replace('-', '').strip(),
        # Datas são mantidas como strings (YYYY-MM-DD) para preencher o input type="date"
        'inicio': form_data.get("inicio"), 
        'termino': form_data.get("termino"), 
        'endereco': form_data.get("endereco", "").strip(),
        'numero': form_data.get("numero", "").strip(),
        'complemento': form_data.get("complemento", "").strip(),
        'bairro': form_data.get("bairro", "").strip(),
        'cidade': form_data.get("cidade", "").strip(),
        'estado': form_data.get("estado", "").strip().upper(),
        # O status é lido do formulário
        'status': 'Ativa' if 'status' in form_data else 'Inativa',
    }

    # 1. Limpeza e Conversão de dados
    try:
        nome = item_form['nome']
        cnpj = item_form['cnpj']
        cep = item_form['cep']
        
        # Converte strings para objetos date para o SQLAlchemy
        inicio = date.fromisoformat(item_form["inicio"])
        termino = date.fromisoformat(item_form["termino"])
        
        endereco = item_form["endereco"]
        numero = item_form["numero"]
        complemento = item_form["complemento"]
        bairro = item_form["bairro"]
        cidade = item_form["cidade"]
        estado = item_form["estado"]
        status = item_form["status"]

    except Exception as e:
        # Se falhar na conversão (ex: data ou campo obrigatório faltando)
        flash("Erro na submissão de dados. Verifique o formato das datas e campos obrigatórios.", "danger")
        # Retorna o template com os dados inválidos para correção
        return render_template("form_obra.html", item=item_form, view_mode=False)

    # 2. Criação ou Edição
    if obra_id:
        # Edição
        obra = Obra.query.get(obra_id)
        if not obra:
            flash("Obra não encontrada para edição.", "danger")
            return redirect(url_for('auth.lista_obras'))
        
        acao = "editada"
        
        # Validação de CNPJ único (apenas se o CNPJ foi alterado)
        if obra.cnpj != cnpj:
            if Obra.query.filter_by(cnpj=cnpj).first():
                flash(f"CNPJ '{cnpj}' já cadastrado em outra obra.", "danger")
                # Retorna para o template de edição com o item_form preenchido
                return render_template("form_obra.html", item=item_form, view_mode=False)
        
        # Atualiza os dados (usa as variáveis convertidas do try block)
        obra.nome = nome
        obra.cnpj = cnpj
        obra.endereco = endereco
        obra.numero = numero
        obra.complemento = complemento
        obra.bairro = bairro
        obra.cidade = cidade
        obra.estado = estado
        obra.cep = cep
        obra.inicio = inicio
        obra.termino = termino
        obra.status = status
        
    else:
        # Criação
        acao = "criada"
        
        # Validação de CNPJ único
        if Obra.query.filter_by(cnpj=cnpj).first():
            flash(f"CNPJ '{cnpj}' já cadastrado.", "danger")
            # Retorna para o template de cadastro com o item_form preenchido
            return render_template("form_obra.html", item=item_form, view_mode=False)
            
        # Cria nova obra
        obra = Obra(
            nome=nome,
            cnpj=cnpj,
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

    # 3. Commit ao Banco de Dados
    try:
        db.session.commit()
        flash(f"Obra '{nome}' {acao} com sucesso!", "success")
        return render_template("form_obra.html", item=item_form, view_mode=True)
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar/editar obra: {e}")
        flash("Ocorreu um erro ao salvar a obra. Tente novamente.", "danger")
        # Em caso de erro de DB, retorna ao template com os dados do formulário
        return render_template("form_obra.html", item=item_form, view_mode=False)

# Rota pra editar obra

@auth_bp.get("/editar-obra/<int:id>")
@login_required
def editar_obra(id):
    from app.models.obra import Obra
    
    item = Obra.query.get_or_404(id)
    
    return render_template("form_obra.html", item=item, categoria="obra")

# Rota para visualizar obra
@auth_bp.get("/visualizar-obra/<int:id>")
@login_required
def visualizar_obra(id):
    from app.models.obra import Obra
    
    # Busca o item de Obra
    item = Obra.query.get_or_404(id) 

    # Define view_mode como True para bloquear os campos no template
    view_mode = True

    # Renderiza o template passando o item e o view_mode
    return render_template("form_obra.html", item=item, view_mode=view_mode, categoria="obra")

