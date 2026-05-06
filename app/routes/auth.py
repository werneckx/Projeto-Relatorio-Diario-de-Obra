# ==============================================================================
# 1. BIBLIOTECAS PADRÃO DO PYTHON
# Ferramentas nativas para manipulação de sistema, data, texto e criptografia.
# ==============================================================================
import os
import re
import json
import base64
import hashlib
import difflib                 # Biblioteca para comparação de textos
import unicodedata
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from math import e
from io import BytesIO
from functools import wraps
from datetime import date, datetime, timedelta, timezone

# ==============================================================================
# 2. FRAMEWORK FLASK E EXTENSÕES
# Funcionalidades principais da web, segurança e banco de dados (SQLAlchemy).
# ==============================================================================
from flask import (
    Blueprint, Config, abort, render_template, request, redirect, 
    url_for, flash, session, send_file, current_app, jsonify, make_response
)
from flask_login import UserMixin, current_user, login_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import extract, func, or_
from sqlalchemy.orm import aliased
from PIL import Image

# ==============================================================================
# 3. CONFIGURAÇÕES DA APLICAÇÃO
# Importações do objeto de aplicação principal e extensões iniciadas.
# ==============================================================================
from app import db, login_manager
from app.forms import LoginForm, RdoForm

# ==============================================================================
# 4. MODELOS DO BANCO DE DADOS (MODELS)
# Definições das tabelas e objetos do sistema.
# ==============================================================================

from app.models.usuario import Usuario, Colaborador, Papel, UsuarioPapel
from app.models.empresa import Empresa
from app.models.auxiliares import AuxClima, AuxFuncoes, AuxEquipamentos, AuxTagOcorrencia
from app.models.obra import FrenteTrabalho, Obra, FrenteColaborador
from app.models.rdo import RDO, RDOAprovacao, RDOEquipamento, RDOMaoObra, RDOAtividade, RDOFoto, RDOOcorrencia
from app.models.fornecedor import Fornecedor

# ==============================================================================
# 5. UTILITÁRIOS E SERVIÇOS
# Funções auxiliares para geração de PDF, QR Codes e lógica de negócios.
# ==============================================================================
from app.utils.qrcode_utils import gerar_qrcode_b64
from app.utils.rdo_pdf import regenerar_pdf_rdo
from app.utils.pdf_service import render_rdo_pdf, render_rdo_pdf_compact
from app.utils.security_pdf import travar_edicao_pdf

# Tenta importar PyMuPDF para highlighting, caso não tenha, segue sem
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Configuração permitida de extensões
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# ==============================================================================
# 6. CONSTANTES DE PERMISSÃO (RBAC) - DEFINIÇÃO DE PAPÉIS
# ==============================================================================
ROLE_ADMIN        = 'ADMIN'
ROLE_GESTOR       = 'GESTOR'
ROLE_OPERADOR     = 'OPERADOR'
ROLE_LEITOR       = 'LEITOR'
ROLE_CLIENTE_OBRA = 'CLIENTE_OBRA'
ROLE_CLIENTE = 'Cliente Obra'

# Grupos de Permissão
# Quem pode escrever dados operacionais (RDO, Equipamentos, etc)
PERM_WRITE_BASIC = [ROLE_ADMIN, ROLE_GESTOR, ROLE_OPERADOR]
# Quem pode gerenciar estrutura (Obras, Usuários)
PERM_MANAGEMENT = [ROLE_ADMIN, ROLE_GESTOR]
# Quem pode apenas visualizar
PERM_VIEW_ONLY = [ROLE_LEITOR, ROLE_CLIENTE]
# Quem pode assinar
PERM_SIGNATURE = [ROLE_ADMIN, ROLE_GESTOR, ROLE_OPERADOR, ROLE_CLIENTE]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#######################################################################################################
####################################################################################################### SECURITY DECORATORS
#######################################################################################################

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Você precisa estar logado para acessar esta página.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

def role_required(allowed_roles):
    """
    Decorator para verificar se o usuário tem um dos papéis permitidos.
    Uso: @role_required([ROLE_ADMIN, ROLE_GESTOR])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for('auth.login'))
            
            user_role = session.get("user_role")
            
            if user_role not in allowed_roles:
                # Log de segurança (opcional)
                print(f"[SECURITY] Acesso negado. User ID: {session.get('user_id')}, Role: {user_role}, Endpoint: {request.endpoint}")
                flash("Acesso não autorizado para o seu perfil de usuário.", "danger")
                return redirect(url_for('auth.inicio'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Helper para verificação de escopo (Scoping)
def get_user_scope_ids():
    """Retorna None para permitir acesso às obras da empresa"""
    # A lógica de scope agora é por empresa_id nas queries.
    return None


def _normalize_option_text(value):
    value = " ".join((value or "").strip().split())
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_value.casefold()


def _normalize_option_input(value):
    return " ".join((value or "").strip().split())


def _find_duplicate_option(model, nome, tipo_lista, exclude_id=None, tipo=None):
    nome_norm = _normalize_option_text(nome)
    tipo_norm = _normalize_option_text(tipo) if tipo else ""

    query = model.query
    if exclude_id:
        query = query.filter(model.id != exclude_id)

    for existing in query.all():
        existing_nome_norm = _normalize_option_text(existing.nome)
        existing_tipo_norm = _normalize_option_text(getattr(existing, "tipo", None))
        if existing_nome_norm == nome_norm and existing_tipo_norm == tipo_norm:
            return existing

    return None


def _normalize_weather_label(label):
    return _normalize_option_text(label).replace("-", " ")


def _classify_weather_code(weather_code):
    if weather_code is None:
        return "Indefinido"

    if weather_code in {95, 96, 99}:
        return "Tempestade"
    if weather_code in {80, 81, 82}:
        return "Chuva"
    if weather_code in {71, 73, 75, 77, 85, 86}:
        return "Neblina"
    if weather_code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67}:
        return "Chuva Leve"
    if weather_code in {45, 48}:
        return "Neblina"
    if weather_code in {1, 2, 3}:
        return "Nublado"
    if weather_code == 0:
        return "Ensolarado"
    return "Indefinido"


def _match_clima_option_id(climas, suggested_label):
    if not suggested_label:
        return None

    suggested_norm = _normalize_weather_label(suggested_label)
    synonym_groups = {
        "ensolarado": ["ensolarado", "sol", "aberto", "ceu limpo", "céu limpo", "limpo"],
        "nublado": ["nublado", "parcialmente nublado", "encoberto", "muitas nuvens", "ublado"],
        "chuva leve": ["chuva leve", "garoa", "chuvisco", "chuva fraca"],
        "chuva": ["chuva", "chuvoso", "pancadas", "pancada"],
        "tempestade": ["tempestade", "trovoada", "temporal"],
        "neblina": ["neblina", "nevoeiro", "névoa", "fog", "bruma"],
        "indefinido": ["indefinido", "variavel", "variável"]
    }

    candidate_terms = synonym_groups.get(suggested_norm, [suggested_norm])
    for clima in climas:
        clima_norm = _normalize_weather_label(clima.nome)
        if clima_norm in candidate_terms:
            return clima.id
        if any(term in clima_norm for term in candidate_terms):
            return clima.id

    return None


def _fetch_json(url, params):
    query_string = urlencode(params)
    with urlopen(f"{url}?{query_string}", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_obra_coordinates(obra):
    uf_to_state = {
        "AC": "acre", "AL": "alagoas", "AP": "amapa", "AM": "amazonas", "BA": "bahia",
        "CE": "ceara", "DF": "distrito federal", "ES": "espirito santo", "GO": "goias",
        "MA": "maranhao", "MT": "mato grosso", "MS": "mato grosso do sul", "MG": "minas gerais",
        "PA": "para", "PB": "paraiba", "PR": "parana", "PE": "pernambuco", "PI": "piaui",
        "RJ": "rio de janeiro", "RN": "rio grande do norte", "RS": "rio grande do sul",
        "RO": "rondonia", "RR": "roraima", "SC": "santa catarina", "SP": "sao paulo",
        "SE": "sergipe", "TO": "tocantins"
    }

    geocode_payload = _fetch_json(
        "https://geocoding-api.open-meteo.com/v1/search",
        {
            "name": obra.cidade,
            "count": 10,
            "language": "pt",
            "format": "json",
        }
    )

    results = geocode_payload.get("results") or []
    obra_estado_norm = _normalize_option_text(obra.estado)
    obra_estado_nome_norm = uf_to_state.get((obra.estado or "").upper(), "")
    for result in results:
        admin1 = _normalize_option_text(result.get("admin1") or "")
        country_code = (result.get("country_code") or "").upper()
        if country_code != "BR":
            continue

        if admin1 == obra_estado_nome_norm or admin1 == obra_estado_norm:
            return result.get("latitude"), result.get("longitude")

    if results:
        first = results[0]
        return first.get("latitude"), first.get("longitude")

    return None, None


def _build_clima_automatico_payload(obra, data_referencia, climas_disponiveis):
    latitude, longitude = _resolve_obra_coordinates(obra)
    if latitude is None or longitude is None:
        raise ValueError("Não foi possível localizar a obra para consulta climática.")

    forecast_payload = _fetch_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "weather_code",
            "timezone": "America/Sao_Paulo",
            "start_date": data_referencia.isoformat(),
            "end_date": data_referencia.isoformat(),
        }
    )

    hourly = forecast_payload.get("hourly") or {}
    times = hourly.get("time") or []
    codes = hourly.get("weather_code") or []
    if not times or not codes:
        raise ValueError("A API climática não retornou dados horários.")

    morning_codes = []
    afternoon_codes = []
    for time_str, code in zip(times, codes):
        hour = int(time_str.split("T")[1].split(":")[0])
        if 6 <= hour <= 11:
            morning_codes.append(code)
        elif 12 <= hour <= 17:
            afternoon_codes.append(code)

    morning_label = _classify_weather_code(max(morning_codes) if morning_codes else None)
    afternoon_label = _classify_weather_code(max(afternoon_codes) if afternoon_codes else None)

    return {
        "manha": {
            "label": morning_label,
            "id": _match_clima_option_id(climas_disponiveis, morning_label)
        },
        "tarde": {
            "label": afternoon_label,
            "id": _match_clima_option_id(climas_disponiveis, afternoon_label)
        }
    }

#######################################################################################################
####################################################################################################### Rota Raiz
#######################################################################################################

@auth_bp.get("/")
def index():
    if "user_id" in session:
        return redirect(url_for("auth.inicio"))
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Login e Logout
#######################################################################################################

@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    from app.routes.admin import seed_system_roles_and_permissions

    # Verifica se já existe algum admin no banco
    admin_exists = Usuario.query.join(Usuario.papeis).filter(
        Papel.nome == ROLE_ADMIN,
        Papel.is_system == True
    ).first()

    if admin_exists:
        flash("O sistema já está configurado.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        empresa_nome = request.form.get("empresa_nome", "").strip()
        admin_nome = request.form.get("admin_nome", "").strip()
        admin_email = request.form.get("admin_email", "").strip()
        admin_senha = request.form.get("admin_senha", "")

        if not all([empresa_nome, admin_nome, admin_email, admin_senha]):
            flash("Todos os campos são obrigatórios.", "danger")
            return render_template("setup.html")

        try:
            # 1. Garantir que roles e permissões globais existam
            seed_system_roles_and_permissions()

            # 2. Criar Empresa principal
            nova_empresa = Empresa(nome=empresa_nome, ativo=True)
            db.session.add(nova_empresa)
            db.session.flush()

            # 3. Criar Colaborador admin
            novo_colab = Colaborador(
                nome=admin_nome,
                empresa_id=nova_empresa.id,
                tipo='PROPRIO',
                ativo=True
            )
            db.session.add(novo_colab)
            db.session.flush()

            # 4. Criar Usuário admin
            novo_user = Usuario(
                email=admin_email,
                empresa_id=nova_empresa.id,
                colaborador_id=novo_colab.id,
                ativo=True,
            )
            novo_user.set_senha(admin_senha)
            db.session.add(novo_user)
            db.session.flush()

            # 5. Buscar papel global ADMIN e vincular ao usuário
            papel_admin = Papel.query.filter_by(nome=ROLE_ADMIN, empresa_id=None).first()
            if papel_admin:
                db.session.add(UsuarioPapel(
                    empresa_id=nova_empresa.id,
                    usuario_id=novo_user.id,
                    papel_id=papel_admin.id,
                    ativo=True
                ))

            db.session.commit()
            flash("Sistema configurado com sucesso! Faça login.", "success")
            return redirect(url_for("auth.login"))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao configurar sistema: {str(e)}", "danger")

    return render_template("setup.html")

@auth_bp.get("/login")
def login():
    admin_exists = Usuario.query.join(Usuario.papeis).filter(Papel.nome == ROLE_ADMIN).first()
    if not admin_exists:
        return redirect(url_for("auth.setup"))
    return render_template("login.html")


@auth_bp.post("/login")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("auth.login"))

    email = form.email.data
    senha = form.senha.data

    # 1. Adicionar o filtro 'ativo=1'
    user = Usuario.query.filter_by(email=email, ativo=True).first()

    # 2. Verificar se o usuário existe e se a senha está correta
    if not user or not user.check_senha(senha):
        flash("E-mail, senha ou status de usuário inválido.", "error")
        return redirect(url_for("auth.login"))
    
    # --- NOVO: REGISTRAR LOG DE ACESSO ---
    try:
        # Captura o IP real, mesmo se estiver atrás de Proxy (Nginx/Cloudflare)
        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if user_ip and ',' in user_ip:
            user_ip = user_ip.split(',')[0].strip()

        # Atualiza os campos no objeto usuário
        # IMPORTANTE: Seu model Usuario deve ter as colunas 'ultimo_acesso' e 'ip_ultimo_acesso'
        user.ultimo_login = datetime.now()
        user.ultimo_login_ip = user_ip
        
        # Salva no banco de dados
        db.session.commit()
    except Exception as e:
        # Se der erro ao salvar o log (ex: coluna não existe), faz rollback mas permite o login
        db.session.rollback()
        print(f"Erro ao salvar log de acesso: {e}")
    # -------------------------------------
    
    # --- LOGIN NO FLASK-LOGIN ---
    login_user(user)
    
    session["user_id"] = user.id
    session["empresa_id"] = user.empresa_id
    session["user_name"] = user.nome
    session["user_email"] = user.email
    session["user_role"] = user.papeis[0].nome if user.papeis else "Leitor"
    
    return redirect(url_for("auth.inicio"))

@auth_bp.get("/logout")
def logout():
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for("auth.login"))

# --- ROTAS DE RECUPERAÇÃO DE SENHA ---

@auth_bp.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    admin_contato = Usuario.query.join(Usuario.papeis).filter(Papel.nome == ROLE_ADMIN).first()

    if request.method == "GET":
        return render_template("esqueci_senha.html", admin=admin_contato)
    
    email = request.form.get("email")
    user = Usuario.query.filter_by(email=email).first()
    
    if user:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps(email, salt='recuperacao-senha')
        link = url_for('auth.redefinir_senha', token=token, _external=True)
        
        print(f"========================================")
        print(f"LINK DE RECUPERAÇÃO PARA {email}:")
        print(f"{link}")
        print(f"========================================")
        
        flash("Um link de recuperação foi enviado para seu e-mail.", "success")
    else:
        flash("Se o e-mail estiver cadastrado, você receberá um link.", "success")
        
    return redirect(url_for("auth.login"))

@auth_bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='recuperacao-senha', max_age=3600)
    except SignatureExpired:
        flash("O link de recuperação expirou.", "danger")
        return redirect(url_for("auth.esqueci_senha"))
    except Exception:
        flash("Link de recuperação inválido.", "danger")
        return redirect(url_for("auth.esqueci_senha"))
    
    if request.method == "GET":
        return render_template("redefinir_senha.html", token=token)
    
    nova_senha = request.form.get("nova_senha")
    confirmar_senha = request.form.get("confirmar_senha")
    
    if nova_senha != confirmar_senha:
        flash("As senhas não conferem.", "danger")
        return render_template("redefinir_senha.html", token=token)
        
    user = Usuario.query.filter_by(email=email).first()
    
    if user:
        user.set_senha(nova_senha)
        db.session.commit()
        flash("Sua senha foi redefinida com sucesso! Faça login.", "success")
        return redirect(url_for("auth.login"))
        
    flash("Erro ao redefinir senha.", "danger")
    return redirect(url_for("auth.login"))

#######################################################################################################
####################################################################################################### Rotas Institucionais
#######################################################################################################

@auth_bp.get("/termos")
def termos():
    return render_template("termos.html")

@auth_bp.get("/privacidade")
def privacidade():
    return render_template("privacidade.html")

@auth_bp.get("/suporte")
def suporte():
    email_usuario = session.get("user_email", "")
    return render_template("suporte.html", email_usuario=email_usuario)

#######################################################################################################
####################################################################################################### Inicio (Dashboard)
#######################################################################################################

@auth_bp.get("/inicio")
@login_required
def inicio():
    hoje = date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month
    
    # SCOPING: Filtra KPIs baseados nas obras permitidas do usuário
    user_id = session.get("user_id")
    user = Usuario.query.get(user_id)
    scope_ids = [o.id for o in Obra.query.filter_by(empresa_id=session.get('empresa_id')).all()] if user.papel != ROLE_ADMIN else None

    # --- 1. KPIs PRINCIPAIS ---
    
    # Query base para Obras
    q_obras = Obra.query.filter_by(empresa_id=session.get('empresa_id'))
    if scope_ids is not None:
        q_obras = q_obras.filter(Obra.id.in_(scope_ids))
    kpi_obras = q_obras.count()
    
    # Query base para RDOs
    q_rdos = RDO.query.filter_by(ativo=True, empresa_id=session.get('empresa_id'))
    if scope_ids is not None:
        q_rdos = q_rdos.filter(RDO.obra_id.in_(scope_ids))
        
    kpi_pendentes = q_rdos.filter_by(status='PENDENTE').count()
    kpi_rdos_mes = q_rdos.filter(
        extract('year', RDO.data_rdo) == ano_atual,
        extract('month', RDO.data_rdo) == mes_atual
    ).count()
    kpi_aprovados_total = q_rdos.filter_by(status='APROVADO').filter(
        extract('year', RDO.data_rdo) == ano_atual
    ).count()
    
    # KPI 3: Efetivo Total (Hoje)
    query_efetivo = db.session.query(
        func.count(RDOMaoObra.id)
    ).join(RDO).filter(RDO.data_rdo == hoje)
    
    if scope_ids is not None:
        query_efetivo = query_efetivo.filter(RDO.obra_id.in_(scope_ids))
        
    kpi_efetivo = query_efetivo.scalar() or 0
    
    # KPI 4: Ocorrências (No Mês Atual)
    query_ocorrencias = db.session.query(func.count(RDOOcorrencia.id))\
        .join(RDO)\
        .filter(extract('year', RDO.data_rdo) == ano_atual)\
        .filter(extract('month', RDO.data_rdo) == mes_atual)
        
    if scope_ids is not None:
        query_ocorrencias = query_ocorrencias.filter(RDO.obra_id.in_(scope_ids))

    kpi_ocorrencias = query_ocorrencias.scalar() or 0

    # --- 2. DADOS PARA INTERATIVIDADE ---
    q_raw = db.session.query(RDO.id, RDO.status, RDO.data_rdo).filter(
        RDO.ativo == True,
        extract('year', RDO.data_rdo) == ano_atual
    )
    if scope_ids is not None:
        q_raw = q_raw.filter(RDO.obra_id.in_(scope_ids))
    raw_rdos = q_raw.all()
    
    dados_graficos_json = [
        {
            'status': str(rdo.status.value) if hasattr(rdo.status, 'value') else str(rdo.status), 
            'mes': rdo.data_rdo.month, 
            'data_iso': rdo.data_rdo.isoformat()
        } 
        for rdo in raw_rdos
        if rdo.data_rdo
    ]

    # --- 3. TABELA DE RESUMO (Últimos Registros) ---
    ultimos_rdos = q_rdos.order_by(RDO.data_rdo.desc(), RDO.id.desc()).limit(5).all()

    return render_template(
        "inicio.html",
        kpi_obras=kpi_obras,
        kpi_pendentes=kpi_pendentes,
        kpi_efetivo=int(kpi_efetivo),
        kpi_ocorrencias=kpi_ocorrencias,
        ultimos_rdos=ultimos_rdos,
        dados_graficos_json=dados_graficos_json,
        kpi_rdos_mes=kpi_rdos_mes,
        kpi_aprovados_total=kpi_aprovados_total
    )
    
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

@auth_bp.get("/gerar-pdf/<int:rdo_id>")
@login_required
def gerar_pdf_rdo_view(rdo_id):
    # SECURITY: Verificar se usuário tem acesso a este RDO
    rdo = RDO.query.get_or_404(rdo_id)
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
        abort(403) # Forbidden

    pdf_content = render_rdo_pdf(rdo_id) 
    try:
        pdf_content = travar_edicao_pdf(pdf_content)
    except Exception as e:
        print(f"Erro ao aplicar segurança no PDF: {e}")
    
    response = make_response(pdf_content)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"{rdo.data.strftime('%d-%m-%Y')} - RDO#{rdo_id} - {rdo.obra.nome if rdo.obra else 'Obra'}.pdf"
    response.headers['Content-Disposition'] = f'inline; filename={filename}'
    
    return response

@auth_bp.get("/gerar-pdf-compacto/<int:rdo_id>")
@login_required
def gerar_pdf_rdo_compacto_view(rdo_id):
    # SECURITY: Verificar scope
    rdo = RDO.query.get_or_404(rdo_id)
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
        abort(403)

    pdf_content = render_rdo_pdf_compact(rdo_id)
    pdf_content = travar_edicao_pdf(pdf_content)
    
    response = make_response(pdf_content)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"RDO_Compacto_{rdo_id}_Bloqueado.pdf"
    response.headers['Content-Disposition'] = f'inline; filename={filename}'
    
    return response

#######################################################################################################
####################################################################################################### RDO (Gestão)
#######################################################################################################

@auth_bp.get("/criar-rdo")
@login_required
@role_required(PERM_WRITE_BASIC) # Leitor e Cliente NÃO criam RDO
def criar_rdo():
    # Carregar apenas obras permitidas
    user = Usuario.query.get(session.get("user_id"))
    if user.papel == ROLE_ADMIN:
        obras = Obra.query.filter_by(status=1).all()
    else:
        # Filtra na memória as obras ativas do usuário
        obras = [o for o in Obra.query.filter_by(empresa_id=session.get('empresa_id')).all() if o.status == 1]
    
    mao_de_obra_options = [{"id": m.id, "nome": m.nome, "tipo": m.tipo} for m in AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()]
    equipamentos_options = [{"id": e.id, "nome": e.nome} for e in AuxEquipamentos.query.filter_by(ativo=True).order_by(AuxEquipamentos.nome.asc()).all()]
    tags_options = [{"id": t.id, "nome": t.nome} for t in AuxTagOcorrencia.query.filter_by(ativo=True).order_by(AuxTagOcorrencia.nome.asc()).all()]

    clima = AuxClima.query.filter_by(ativo=True).order_by(AuxClima.nome.asc()).all()
    frente_trabalho = FrenteTrabalho.query.all() 
    usuarios_obra = Usuario.query.all()

    return render_template(
        "form_rdo.html", 
        item=None, 
        obras=obras, 
        clima=clima, 
        frente_trabalho=frente_trabalho, 
        usuarios_obra=usuarios_obra,
        view_mode=False,
        mao_de_obra_options=mao_de_obra_options,
        equipamentos_options=equipamentos_options, 
        tags_options=tags_options 
    )


def _get_equipe_obra_payload(obra_id):
    equipe = (
        db.session.query(EquipeObraMaoObra, MaoObra)
        .join(MaoObra, AuxFuncoes.id == EquipeObraAuxFuncoes.id_lista_opcoes)
        .filter(EquipeObraAuxFuncoes.obra_id == obra_id, AuxFuncoes.ativo == True)
        .order_by(AuxFuncoes.nome.asc())
        .all()
    )

    return [
        {
            "id_equipe_obra": equipe_item.id_equipe_obra,
            "id_lista_opcoes": mao_item.id,
            "nome": mao_item.nome,
            "tipo": mao_item.tipo,
            "quantidade": equipe_item.quantidade_mao_obra,
        }
        for equipe_item, mao_item in equipe
    ]

@auth_bp.get("/api/obra/<int:id>")
@login_required
def get_obra_api(id):
    # SECURITY: Verifica se usuário pode ver detalhes desta obra
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return jsonify({"error": "Acesso não autorizado a esta obra"}), 403

    obra = Obra.query.get_or_404(id)
    frentes = FrenteTrabalho.query.filter_by(obra_id=id).all()
    
    data_inicio_fmt = obra.data_inicio.strftime('%d/%m/%Y') if obra.data_inicio else "-"
    data_inicio_iso = obra.data_inicio.isoformat() if obra.data_inicio else ""
    data_fim_fmt = obra.data_fim.strftime('%d/%m/%Y') if obra.data_fim else "-"
    data_fim_iso = obra.data_fim.isoformat() if obra.data_fim else ""
    nome_responsavel = obra.responsavel.nome if obra.responsavel else "Não definido"

    lista_frentes = []
    for f in frentes:
        nome_resp_frente = f.responsavel.nome if f.responsavel else "Sem responsável"
        id_resp_frente = f.criado_por if f.criado_por else ""
        lista_frentes.append({
            "id": f.id,
            "nome": f.nome,
            "centro_custo": f.centro_custo or "",
        })

    return jsonify({
        "data_inicio": data_inicio_fmt,
        "data_inicio_iso": data_inicio_iso,
        "data_fim": data_fim_fmt,
        "data_fim_iso": data_fim_iso,
        "horario_entrada": obra.hora_entrada_padrao.strftime('%H:%M') if obra.hora_entrada_padrao else "",
        "horario_saida": obra.hora_saida_padrao.strftime('%H:%M') if obra.hora_saida_padrao else "",
        "responsavel_id": obra.criado_por,
        "frentes": lista_frentes,
    })


@auth_bp.get("/api/obra/<int:id>/clima")
@login_required
def get_obra_clima_api(id):
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return jsonify({"error": "Acesso não autorizado a esta obra"}), 403

    obra = Obra.query.get_or_404(id)
    data_str = request.args.get("data")
    try:
        data_referencia = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else date.today()
    except ValueError:
        return jsonify({"error": "Data inválida. Use o formato YYYY-MM-DD."}), 400

    climas_disponiveis = AuxClima.query.filter_by(ativo=True).order_by(AuxClima.nome.asc()).all()

    try:
        payload = _build_clima_automatico_payload(obra, data_referencia, climas_disponiveis)
        payload["obra"] = {"nome": obra.nome}
        payload["data"] = data_referencia.isoformat()
        payload["matched"] = bool(payload["manha"]["id"] or payload["tarde"]["id"])
        return jsonify(payload)
    except (URLError, HTTPError, TimeoutError, ValueError) as exc:
        current_app.logger.warning(f"Falha ao consultar clima automático da obra {id}: {exc}")
        return jsonify({"error": str(exc)}), 502

@auth_bp.get("/api/frente/<int:id>")
@login_required
def get_frente_api(id):
    # SECURITY: Validação básica
    frente = FrenteTrabalho.query.get_or_404(id)
    # Verifica scope da obra pai da frente
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and frente.obra_id not in scope_ids:
        return jsonify({"error": "Forbidden"}), 403

    return jsonify({
        "nome": frente.nome,
        "centro_custo": frente.centro_custo or ""
    })

@auth_bp.post("/gerar-rdo")
@login_required
@role_required(PERM_WRITE_BASIC) # Leitor e Cliente não podem postar
def gerar_rdo():
    try:
        sp_tz = timezone(timedelta(hours=-3))
        now_br = datetime.now(sp_tz).replace(tzinfo=None)
        current_user_id = session.get("user_id")

        form = RdoForm()
        if not form.validate_on_submit():
            for field_errors in form.errors.values():
                for error in field_errors:
                    flash(error, "danger")
            return redirect(request.referrer or url_for('auth.criar_rdo'))

        # Helpers
        def _get_int(key):
            v = request.form.get(key)
            return int(v) if v and v.isdigit() else None
        
        def _get_time(key):
            v = request.form.get(key)
            if not v: return None
            try: return datetime.strptime(v, '%H:%M').time()
            except: return None
            
        def _get_float(key):
            v = request.form.get(key)
            if not v: return None
            try: return float(v.replace(',', '.'))
            except: return None

        def _get_float_from_list(values, index):
            if index >= len(values) or not values[index]:
                return None
            try:
                return float(values[index].replace(',', '.'))
            except Exception:
                return None

        rdo_id_original = _get_int("rdo_id")
        obra_id = _get_int("obra_id")

        # SECURITY: Validação de Escopo (Data Scoping)
        # Verifica se o usuário tem permissão na Obra alvo
        scope_ids = get_user_scope_ids()
        if scope_ids is not None:
            if obra_id not in scope_ids:
                flash("Você não tem permissão para criar/editar RDO nesta obra.", "danger")
                abort(403)

        # SECURITY: Se for edição, verifica status e permissões extras
        if rdo_id_original:
            item_rdo = RDO.query.get(rdo_id_original)
            if not item_rdo:
                abort(404)
            
            # Se já aprovado, apenas Admin/Gestor podem revisar (Operador não revisa aprovado, cria novo geralmente)
            if item_rdo.status == 'APROVADO' and session.get("user_role") == ROLE_OPERADOR:
                 flash("Operadores não podem alterar RDOs já aprovados. Solicite ao Gestor.", "danger")
                 return redirect(url_for('auth.visualizar_rdo', rdo_id=rdo_id_original))

            # UPDATE (EDIÇÃO / NOVA REVISÃO)
            item_rdo.status = 'PENDENTE'

            # Reset workflow
            assinaturas_existentes = RDOAprovacao.query.filter_by(rdo_id=item_rdo.id).all()
            for ass in assinaturas_existentes:
                ass.imagem_assinatura = None
                ass.comentario = None
                ass.status = 'PENDENTE'
                ass.data_aprovacao = None
                ass.endereco_ip = None
                ass.hash = None

        else:
            # INSERT (NOVO RDO)
            item_rdo = RDO(
                empresa_id=session.get('empresa_id'),
                obra_id=obra_id,
            )
            item_rdo.criado_por = current_user_id
            item_rdo.status = 'PENDENTE'

        # Popular campos comuns
        item_rdo.frente_trabalho_id = _get_int("frente_trabalho_id")
        item_rdo.clima_manha_id = _get_int("climas_manha")
        item_rdo.clima_tarde_id = _get_int("climas_tarde")
        data_rdo_str = request.form.get("data_rdo")
        item_rdo.data_rdo = datetime.strptime(data_rdo_str, '%Y-%m-%d').date() if data_rdo_str else date.today()
        item_rdo.modificado_por = current_user_id
        item_rdo.observacoes = request.form.get("comentarios_gerais")
        item_rdo.hora_entrada = _get_time("hora_entrada")
        item_rdo.hora_saida = _get_time("hora_saida")
        item_rdo.intervalo_entrada = _get_time("intervalo_entrada")
        item_rdo.intervalo_saida = _get_time("intervalo_saida")
        
        if not rdo_id_original:
            db.session.add(item_rdo)
        
        db.session.flush()

        # [Criação] Assinatura do criador
        if not rdo_id_original:
            obra_rdo = Obra.query.get(obra_id) if obra_id else None
            aprovador_padrao_id = obra_rdo.criado_por if obra_rdo and obra_rdo.criado_por else current_user_id
            existe_ass = RDOAprovacao.query.filter_by(rdo_id=item_rdo.id, aprovador_id=aprovador_padrao_id).first()
            if not existe_ass:
                assinatura_criador = RDOAprovacao(
                    empresa_id=session.get('empresa_id'),
                    rdo_id=item_rdo.id,
                    aprovador_id=aprovador_padrao_id,
                    nivel=1,
                    status='PENDENTE',
                    ativo=True
                )
                db.session.add(assinatura_criador)

        # Limpeza de filhos para recriação
        if rdo_id_original:
            RDOAtividade.query.filter_by(rdo_id=item_rdo.id).delete()
            RDOMaoObra.query.filter_by(rdo_id=item_rdo.id).delete()
            RDOEquipamento.query.filter_by(rdo_id=item_rdo.id).delete()
            RDOOcorrencia.query.filter_by(rdo_id=item_rdo.id).delete()

        # 1. Atividades
        descricoes = request.form.getlist("atividade_descricao[]")
        status_list = request.form.getlist("atividade_status[]")
        for i, desc in enumerate(descricoes):
            if desc and desc.strip():
                st = status_list[i] if i < len(status_list) else "Não iniciada"
                db.session.add(RDOAtividade(
                    empresa_id=session.get('empresa_id'),
                    rdo_id=item_rdo.id,
                    descricao=desc,
                    status=st,
                    ativo=True,
                ))

        mo_colaborador_ids = request.form.getlist("mo_colaborador_id[]")
        mo_funcoes = request.form.getlist("mo_funcao[]")
        mo_horas = request.form.getlist("mo_horas[]")
        mo_tipos = request.form.getlist("mo_tipo[]")
        for i, col_id in enumerate(mo_colaborador_ids):
            if col_id and col_id.isdigit():
                db.session.add(
                    RDOMaoObra(
                        empresa_id=session.get('empresa_id'),
                        rdo_id=item_rdo.id,
                        colaborador_id=int(col_id),
                        funcao=mo_funcoes[i] if i < len(mo_funcoes) else None,
                        quantidade_horas=_get_float_from_list(mo_horas, i),
                        tipo_mao_obra=mo_tipos[i] if i < len(mo_tipos) else 'PROPRIA',
                        ativo=True
                    )
                )

        # 3. Equipamentos
        eq_ids = request.form.getlist("eq_id[]")
        eq_qts = request.form.getlist("eq_qtd[]")
        eq_status_list = request.form.getlist("eq_status[]")
        for i, eid in enumerate(eq_ids):
            if eid and eid.isdigit():
                qtd = int(eq_qts[i]) if i < len(eq_qts) and eq_qts[i] else 0
                eq_status = eq_status_list[i] if i < len(eq_status_list) else 'OPERANDO'
                db.session.add(RDOEquipamento(
                    empresa_id=session.get('empresa_id'),
                    rdo_id=item_rdo.id,
                    equipamento_id=int(eid),
                    quantidade=qtd,
                    status=eq_status,
                    ativo=True
                ))

        # 4. Ocorrências
        oc_tags = request.form.getlist("oc_tag[]")
        oc_descs = request.form.getlist("oc_desc[]")
        oc_impactos = request.form.getlist("oc_impacto[]")
        oc_tempos = request.form.getlist("oc_tempo_parado[]")
        for i, tid in enumerate(oc_tags):
            if not tid: continue
            tempo_par = None
            tempo_str = oc_tempos[i] if i < len(oc_tempos) else None
            if tempo_str and tempo_str.strip():
                try: tempo_par = float(tempo_str.replace(',','.'))
                except ValueError: tempo_par = None
            desc = oc_descs[i] if i < len(oc_descs) else ""
            impacto = oc_impactos[i] if i < len(oc_impactos) else None
            db.session.add(RDOOcorrencia(
                empresa_id=session.get('empresa_id'),
                rdo_id=item_rdo.id,
                tipo_ocorrencia=int(tid) if tid.isdigit() else None,
                descricao=desc,
                impacto=impacto,
                tempo_paralisacao=tempo_par,
                ativo=True
            ))

        # 5. Fotos
        UPLOAD_FOLDER = os.path.join(current_app.root_path, 'static', 'uploads', 'rdo')
        if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
            
        ids_remover = request.form.getlist("fotos_remover[]")
        if ids_remover:
            for id_rem in ids_remover:
                try:
                    if not id_rem: continue
                    foto_del = RDOFoto.query.get(int(id_rem))
                    if foto_del and foto_del.rdo_id == item_rdo.id:
                        try:
                            caminho_arquivo = os.path.join(UPLOAD_FOLDER, foto_del.arquivo)
                            if os.path.exists(caminho_arquivo): os.remove(caminho_arquivo)
                        except Exception: pass
                        db.session.delete(foto_del)
                except Exception: pass
            
        ids_existentes = request.form.getlist("fotos_existentes_ids[]")
        comentarios_existentes = request.form.getlist("comentarios_existentes_list[]")
        for foto_id_str, nova_legenda in zip(ids_existentes, comentarios_existentes):
            try:
                if not foto_id_str: continue
                foto_id = int(foto_id_str)
                foto_obj = RDOFoto.query.get(foto_id)
                if foto_obj and foto_obj.rdo_id == item_rdo.id:
                    if foto_obj.comentario != nova_legenda:
                        foto_obj.comentario = nova_legenda
                        db.session.add(foto_obj)
            except Exception: pass

        arquivos = request.files.getlist("fotos[]")
        legendas = request.form.getlist("novas_fotos_comentarios[]")
        idx_file = 0
        for arquivo in arquivos:
            if arquivo and arquivo.filename:
                fname = secure_filename(arquivo.filename)
                ext = os.path.splitext(fname)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f')
                    novo_nome = f"{timestamp}_{idx_file}{ext}"
                    caminho_salvar = os.path.join(UPLOAD_FOLDER, novo_nome)

                    try:
                        img = Image.open(arquivo)
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        img.thumbnail((1920, 1080), Image.LANCZOS)
                        img.save(caminho_salvar, optimize=True, quality=75)
                    except Exception:
                        arquivo.stream.seek(0)
                        arquivo.save(caminho_salvar)

                    comentario = legendas[idx_file] if idx_file < len(legendas) else ""
                    db.session.add(RDOFoto(
                        empresa_id=session.get('empresa_id'),
                        rdo_id=item_rdo.id,
                        arquivo=novo_nome,
                        comentario=comentario,
                        ativo=True,
                    ))
                    idx_file += 1

        db.session.commit()
        msg_acao = "revisado" if rdo_id_original else "salvo"
        flash(f"RDO #{item_rdo.id} {msg_acao} com sucesso!", "success")
        return redirect(url_for('auth.visualizar_rdo', rdo_id=item_rdo.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao gerar RDO: {e}")
        import traceback
        traceback.print_exc()
        flash(f"Erro ao salvar RDO: {str(e)}", "danger")
        return redirect(request.referrer)
    
@auth_bp.get("/visualizar-rdo/<int:rdo_id>")
@login_required
def visualizar_rdo(rdo_id):
    item = RDO.query.filter_by(id=rdo_id, ativo=True).first_or_404()

    # SECURITY: Verifica permissão na obra para leitura
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and item.obra_id not in scope_ids:
        flash("Você não tem permissão para visualizar este RDO.", "danger")
        return redirect(url_for("auth.inicio"))

    selected_equip_ids = [eq.equipamento_id for eq in item.equipamentos if eq.equipamento_id]
    selected_tag_ids = [oc.tipo_ocorrencia for oc in item.ocorrencias if oc.tipo_ocorrencia]
    selected_clima_ids = [cid for cid in [item.clima_manha_id, item.clima_tarde_id] if cid]

    mao_de_obra_options = [{"id": m.id, "nome": m.descricao, "tipo": m.tipo} for m in AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.descricao.asc()).all()]
    equipamentos_options = [{"id": e.id, "nome": e.descricao} for e in AuxEquipamentos.query.filter(
        or_(AuxEquipamentos.ativo == True, AuxEquipamentos.id.in_(selected_equip_ids))
    ).order_by(AuxEquipamentos.descricao.asc()).all()]
    tags_options = [{"id": t.id, "nome": t.descricao} for t in AuxTagOcorrencia.query.filter(
        or_(AuxTagOcorrencia.ativo == True, AuxTagOcorrencia.id.in_(selected_tag_ids))
    ).order_by(AuxTagOcorrencia.descricao.asc()).all()]
    clima = AuxClima.query.filter(
        or_(AuxClima.ativo == True, AuxClima.id.in_(selected_clima_ids))
    ).order_by(AuxClima.nome.asc()).all()
    assinaturas = RDOAprovacao.query.filter_by(rdo_id=rdo_id).order_by(RDOAprovacao.nivel).all()
    
    if item.obra_id:
        usuarios_obra = Usuario.query.filter_by(
            empresa_id=session.get('empresa_id'), ativo=True
        ).all()
    else:
        usuarios_obra = Usuario.query.filter_by(
            empresa_id=session.get('empresa_id'), ativo=True
        ).all()
    
    ass_valida = RDOAprovacao.query.filter_by(rdo_id=rdo_id, status='APROVADO').order_by(RDOAprovacao.nivel.desc()).first()
    if ass_valida and ass_valida.hash:
        url_validacao = url_for('auth.validar_documento_publico', h=ass_valida.hash, _external=True)
    else:
        url_validacao = url_for('auth.visualizar_rdo', rdo_id=rdo_id, _external=True)

    qr_code_img = gerar_qrcode_b64(url_validacao)

    return render_template(
        "form_rdo.html",
        item=item,
        view_mode=True,
        obras=Obra.query.all(),
        clima=AuxClima.query.filter_by(ativo=True).order_by(AuxClima.nome.asc()).all(),
        frente_trabalho=FrenteTrabalho.query.filter_by(empresa_id=session.get('empresa_id')).all(),
        equipamentos=AuxEquipamentos.query.filter_by(ativo=True).all(),
        assinaturas=assinaturas,
        mao_obra=RDOMaoObra.query.all(),
        usuarios=Usuario.query.all(),
        usuarios_obra=usuarios_obra,
        mao_de_obra_options=mao_de_obra_options,
        equipamentos_options=equipamentos_options,
        tags_options=tags_options,
        qr_code_b64=qr_code_img
    )

@auth_bp.get("/editar-rdo/<int:rdo_id>")
@login_required
@role_required(PERM_WRITE_BASIC) # Leitor e Cliente não editam
def editar_rdo(rdo_id):
    item = RDO.query.filter_by(id=rdo_id, ativo=True).first_or_404()

    # SECURITY: Verifica se usuario tem acesso à obra deste RDO
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and item.obra_id not in scope_ids:
        abort(403)

    usuarios_obra = Usuario.query.filter_by(
        empresa_id=session.get('empresa_id'), ativo=True
    ).all()
    assinaturas_realizadas = RDOAprovacao.query.filter_by(rdo_id=rdo_id).all()
    ids_usuarios_que_assinaram = [a.aprovador_id for a in assinaturas_realizadas]

    lista_assinaturas_status = []
    for u in usuarios_obra:
        ass_obj = next((a for a in assinaturas_realizadas if a.aprovador_id == u.id), None)
        if u.id == item.criado_por or u.id in ids_usuarios_que_assinaram or (u.papeis and any(p.nome in [ROLE_ADMIN, ROLE_GESTOR] for p in u.papeis)):
            lista_assinaturas_status.append({
                "usuario": u,
                "assinado": True if ass_obj else False,
                "dados_assinatura": ass_obj
            })

    maos_obra_salvas = item.maos_obra.all()
    equipamentos_salvos = item.equipamentos.all()
    atividades_salvas = item.atividades.all()
    ocorrencias_salvas = item.ocorrencias.all()
    fotos_salvas = item.fotos.all()
    frente_trabalho=FrenteTrabalho.query.all()

    return render_template(
        "form_rdo.html",
        item=item,
        view_mode=False,
        obras=Obra.query.filter_by(empresa_id=session.get('empresa_id'), ativo=True).all(),
        frente_trabalho=frente_trabalho,
        clima=AuxClima.query.filter(
            or_(AuxClima.ativo == True, AuxClima.id.in_([cid for cid in [item.clima_manha_id, item.clima_tarde_id] if cid]))
        ).order_by(AuxClima.nome.asc()).all(),
        maos_obra_salvas=maos_obra_salvas,
        equipamentos_salvos=equipamentos_salvos,
        atividades_salvas=atividades_salvas,
        ocorrencias_salvas=ocorrencias_salvas,
        fotos_salvas=fotos_salvas,
        mao_de_obra_options=[{"id": m.id, "nome": m.nome, "tipo": m.tipo} for m in AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()],
        equipamentos_options=[{"id": e.id, "nome": e.descricao} for e in AuxEquipamentos.query.filter(
            or_(AuxEquipamentos.ativo == True, AuxEquipamentos.id.in_([eq.equipamento_id for eq in equipamentos_salvos if eq.equipamento_id]))
        ).order_by(AuxEquipamentos.descricao.asc()).all()],
        tags_options=[{"id": t.id, "nome": t.descricao} for t in AuxTagOcorrencia.query.filter(
            or_(AuxTagOcorrencia.ativo == True, AuxTagOcorrencia.id.in_([oc.tipo_ocorrencia for oc in ocorrencias_salvas if oc.tipo_ocorrencia]))
        ).order_by(AuxTagOcorrencia.descricao.asc()).all()],
        usuarios_obra=usuarios_obra,
        lista_assinaturas_status=lista_assinaturas_status,
        assinaturas=assinaturas_realizadas
    )

@auth_bp.post("/excluir-rdo/<int:rdo_id>")
@login_required
@role_required(PERM_MANAGEMENT) # SECURITY: Apenas Admin/Gestor exclui RDO (Operador não)
def excluir_rdo(rdo_id):
    try:
        item_rdo = RDO.query.get_or_404(rdo_id)
        
        # SECURITY: Scoping Check
        scope_ids = get_user_scope_ids()
        if scope_ids is not None and item_rdo.obra_id not in scope_ids:
            abort(403)

        item_rdo.ativo = False
        item_rdo.modificado_por = session.get('user_id')
        db.session.commit()

        flash(f"RDO #{item_rdo.id} enviado para lixeira com sucesso!", "success")
        return redirect(url_for('auth.inicio'))
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao excluir o RDO: {str(e)}", "danger")
        return redirect(url_for('auth.inicio'))

@auth_bp.get("/lista-rdo")
@login_required
def lista_rdo():
    current_user_id = session.get("user_id")
    user = Usuario.query.get(current_user_id)

    # SCOPING: Filtra RDOs ativos
    if user:
        if user.papel == ROLE_ADMIN:
             rdos = RDO.query.filter_by(ativo=True).order_by(RDO.data_rdo.desc()).all()
        else:
            ids_obras_permitidas = [obra.id for obra in user.obras_permitidas]
            rdos = RDO.query.filter(RDO.obra_id.in_(ids_obras_permitidas), RDO.ativo == True).order_by(RDO.data_rdo.desc()).all()
    else:
        rdos = []
    
    lista_pendencias = RDOAprovacao.query.filter_by(
        aprovador_id=current_user_id, 
        status='PENDENTE',
        ativo=True
    ).all()
    
    minhas_pendencias = RDOAprovacao.query.filter_by(
        aprovador_id=current_user_id,
        status='PENDENTE',
        ativo=True
    ).count()

    return render_template("list_rdo.html", rdos=rdos, count_minhas_pendencias=minhas_pendencias, lista_pendencias=lista_pendencias)

#######################################################################################################
####################################################################################################### Assinaturas RDO
#######################################################################################################

@auth_bp.route("/assinar-rdo/<int:rdo_id>/salvar-workflow", methods=["POST"])
@login_required
@role_required(PERM_MANAGEMENT) # Apenas Gestor/Admin define fluxo
def salvar_workflow_assinaturas(rdo_id):
    rdo = RDO.query.filter_by(id=rdo_id, ativo=True).first_or_404()
    
    # Scoping
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
        return jsonify({"success": False, "message": "Sem permissão na obra."}), 403
    
    if rdo.status in ['APROVADO', 'REJEITADO']:
         return jsonify({"success": False, "message": "RDO finalizado, não é possível alterar aprovadores."}), 403

    data = request.get_json()
    novos_assinantes_ids = [int(uid) for uid in data.get('usuarios_ids', [])] 
    
    owner_id = rdo.obra.criado_por if rdo.obra and rdo.obra.criado_por else rdo.id_criado_por
    if owner_id in novos_assinantes_ids:
        novos_assinantes_ids.remove(owner_id)
    if owner_id:
        novos_assinantes_ids.insert(0, owner_id)

    try:
        RDOAprovacao.query.filter_by(rdo_id=rdo_id).delete()
        for index, user_id in enumerate(novos_assinantes_ids):
            nova_ass = RDOAprovacao(
                empresa_id=session.get('empresa_id'),
                rdo_id=rdo_id,
                aprovador_id=user_id,
                nivel=index + 1,
                status='PENDENTE',
                ativo=True
            )
            db.session.add(nova_ass)
        rdo.status = 'PENDENTE'
        db.session.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@auth_bp.route("/assinar-rdo/<int:rdo_id>/aprovar-rdo", methods=["POST"])
@login_required
@role_required(PERM_SIGNATURE) # Todos (exceto Leitor) podem assinar se estiverem no fluxo
def assinar_rdo(rdo_id):
    user_id = session.get("user_id")
    rdo = RDO.query.filter_by(id=rdo_id, ativo=True).first_or_404()

    # Scoping check: Tem que ter acesso à obra pra assinar
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
         return jsonify({"success": False, "message": "Sem permissão na obra."}), 403

    assinatura_pendente = RDOAprovacao.query.filter_by(
        rdo_id=rdo_id, 
        aprovador_id=user_id, 
        status='PENDENTE',
        ativo=True
    ).first()

    if not assinatura_pendente:
        return jsonify({"success": False, "message": "Você não tem assinaturas pendentes para este RDO."}), 400

    passo_anterior_pendente = RDOAprovacao.query.filter(
        RDOAprovacao.rdo_id == rdo_id,
        RDOAprovacao.nivel < assinatura_pendente.nivel,
        RDOAprovacao.status != 'APROVADO',
        RDOAprovacao.ativo == True
    ).count()

    if passo_anterior_pendente > 0:
        return jsonify({"success": False, "message": "Aguarde a aprovação do responsável anterior."}), 403

    dados = request.get_json()
    img_data = dados.get('assinatura_b64')
    latitude = dados.get('latitude')
    longitude = dados.get('longitude')
    
    if not img_data:
        return jsonify({"success": False, "message": "Imagem da assinatura não fornecida."}), 400

    try:
        header, encoded = img_data.split(",", 1)
        file_data = base64.b64decode(encoded)
        filename = f"sig_{rdo_id}_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'assinaturas')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        with open(os.path.join(upload_folder, filename), "wb") as f:
            f.write(file_data)

        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if user_ip and ',' in user_ip:
            user_ip = user_ip.split(',')[0].strip()

        hash_string = f"{rdo_id}:{user_id}:{datetime.utcnow()}:{current_app.config['SECRET_KEY']}"
        document_hash = hashlib.sha256(hash_string.encode()).hexdigest()

        assinatura_pendente.imagem_assinatura = filename
        assinatura_pendente.data_aprovacao = datetime.now()
        assinatura_pendente.status = 'APROVADO'
        assinatura_pendente.endereco_ip = user_ip
        # RDOAprovacao não possui latitude e longitude
        # assinatura_pendente.latitude = latitude
        # assinatura_pendente.longitude = longitude
        assinatura_pendente.hash = document_hash 
        
        restantes = RDOAprovacao.query.filter(
            RDOAprovacao.rdo_id == rdo_id,
            RDOAprovacao.status == 'PENDENTE',
            RDOAprovacao.id != assinatura_pendente.id,
            RDOAprovacao.ativo == True
        ).count()
        
        if restantes == 0:
            rdo.status = 'APROVADO'
        else:
            rdo.status = 'PENDENTE'

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    
@auth_bp.route("/assinar-rdo/<int:id_assinatura>/rejeitar-rdo", methods=["POST"])
@login_required
@role_required(PERM_SIGNATURE)
def rejeitar_assinatura(id_assinatura):
    dados = request.get_json()
    motivo = dados.get('motivo')
    ass = RDOAprovacao.query.get_or_404(id_assinatura)
    
    if ass.aprovador_id != session.get('user_id'):
        return jsonify({"success": False, "message": "Não autorizado."}), 403

    try:
        ass.status = 'REJEITADO'
        ass.comentario = motivo
        ass.data_aprovacao = datetime.now()
        rdo = RDO.query.get(ass.rdo_id)
        rdo.status = 'REJEITADO'
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    
#######################################################################################################
####################################################################################################### USUARIOS
#######################################################################################################

@auth_bp.get("/lista-usuarios")
@login_required
@role_required(PERM_WRITE_BASIC) # Leitor e Cliente não veem usuários
def lista_usuarios():
    # SCOPING: Gestor/Operador só veem usuários de suas obras
    query = Usuario.query
    if session.get("user_role") != ROLE_ADMIN:
        user = Usuario.query.get(session.get("user_id"))
        ids_permitidos = [o.id for o in Obra.query.filter_by(empresa_id=session.get('empresa_id')).all()]
        # Filtra usuários que tenham intersecção de obras (usuários da mesma obra)
        query = query.filter(Usuario.obras_permitidas.any(Obra.id.in_(ids_permitidos)))

    usuarios = query.order_by(Usuario.id.asc()).all()

    # Preenchimento de supervisor (mantido)
    sup_ids = set()
    for u in usuarios:
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_ids.add(int(str(u.id_supervisor).strip()))
        except Exception: continue

    sup_map = {}
    if sup_ids:
        supervisors = Usuario.query.filter(Usuario.id.in_(list(sup_ids))).all()
        sup_map = {s.id: s.nome for s in supervisors}

    for u in usuarios:
        nome_sup = None
        try:
            if u.id_supervisor is not None and str(u.id_supervisor).strip() != '':
                sup_id = int(str(u.id_supervisor).strip())
                nome_sup = sup_map.get(sup_id)
        except Exception: pass
        setattr(u, 'nome_supervisor', nome_sup)

    return render_template("list_usuarios.html", opcoes=usuarios, categoria="usuario")

@auth_bp.get("/criar-usuario")
@login_required
@role_required(PERM_MANAGEMENT) # Apenas Admin e Gestor criam
def criar_usuario():
    # SCOPING: Gestor só pode vincular às suas obras
    user = Usuario.query.get(session.get("user_id"))
    if user.papel == ROLE_ADMIN:
        obras = Obra.query.filter_by(status=1).order_by(Obra.nome).all()
    else:
        obras = [o for o in Obra.query.filter_by(empresa_id=session.get('empresa_id')).all() if o.status == 1]
    
    admin = Usuario.query.filter_by(papel='Admin').first()
    default_supervisor = {'id': admin.id, 'nome': admin.nome, 'email': admin.email} if admin else None

    return render_template(
        "form_usuario.html", 
        categoria="usuario", 
        obras=obras,
        default_supervisor=default_supervisor
    )

@auth_bp.post("/gerar-usuario")
@login_required
@role_required(PERM_MANAGEMENT)
def gerar_usuario():
    categoria = request.form.get("categoria")
    user_id = request.form.get("id")
    current_user_obj = Usuario.query.get(session.get("user_id"))
    
    # SCOPING: Para reload do template em caso de erro
    if current_user_obj.papel == ROLE_ADMIN:
        obras_ativas = Obra.query.filter_by(status=1).order_by(Obra.nome).all()
    else:
        obras_ativas = [o for o in current_user_obj.obras_permitidas if o.status == 1]

    if categoria == "usuario":
        nome = request.form.get("nome")
        email = request.form.get("email")
        papel = request.form.get("papel")
        cpf = request.form.get("cpf") 
        senha = request.form.get("senha")
        status = True if request.form.get("status") == "on" else False
        obras_ids = request.form.getlist("obras_permitidas")
        id_supervisor_raw = request.form.get('id_supervisor')

        # SECURITY: Gestor não pode criar Admin
        if current_user_obj.papel == ROLE_GESTOR and papel == ROLE_ADMIN:
            flash("Gestores não podem criar usuários Administradores.", "danger")
            return render_template("form_usuario.html", item=None, obras=obras_ativas)

        item_form = {'id': user_id, 'nome': nome, 'email': email, 'papel': papel, 'cpf': cpf}

        if user_id:
            user = Usuario.query.get_or_404(user_id)
            # Validar se Gestor pode editar este usuário
            if current_user_obj.papel != ROLE_ADMIN:
                # Simplificação: Se o usuário alvo tem alguma obra em comum, permite (ou restringe mais conforme regra)
                # Por segurança, impede edição de admin por gestor
                if user.papel == ROLE_ADMIN:
                    flash("Gestores não podem editar Admins.", "danger")
                    return redirect(url_for('auth.lista_usuarios'))

            if Usuario.query.filter(Usuario.cpf == cpf, Usuario.id != user_id).first():
                flash("Este CPF já está cadastrado.", "danger")
                return render_template("form_usuario.html", item=item_form, obras=obras_ativas)
            
            user.nome, user.email, user.papel, user.cpf, user.status = nome, email, papel, cpf, status
            try: user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception: user.id_supervisor = None
        else:
            if Usuario.query.filter_by(cpf=cpf).first():
                flash("CPF já cadastrado.", "danger")
                return render_template("form_usuario.html", item=item_form, obras=obras_ativas)

            user = Usuario(nome=nome, email=email, papel=papel, cpf=cpf, status=status, primeiro_acesso=True)
            try: user.id_supervisor = int(id_supervisor_raw) if id_supervisor_raw else None
            except Exception: user.id_supervisor = None
            user.set_senha(senha if senha else "Usuario123")
            db.session.add(user)

        if papel == 'Admin':
            user.obras_permitidas = Obra.query.all()
        else:
            obras_selecionadas = []
            if obras_ids:
                # SECURITY: Garantir que Gestor só vincula obras que ele tem acesso
                allowed_ids = [o.id for o in obras_ativas]
                for oid in obras_ids:
                    if oid:
                        if current_user_obj.papel == ROLE_ADMIN or int(oid) in allowed_ids:
                            obra = Obra.query.get(int(oid))
                            if obra: obras_selecionadas.append(obra)
            user.obras_permitidas = obras_selecionadas

        if not getattr(user, 'id_supervisor', None):
            try:
                admin = Usuario.query.filter_by(papel='Admin').first()
                if admin: user.id_supervisor = admin.id
            except Exception: pass

        try:
            db.session.commit()
            flash("Usuário salvo com sucesso!", "success")
            return render_template("form_usuario.html", item=user, obras=obras_ativas, view_mode=True)
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
            return render_template("form_usuario.html", item=item_form, obras=obras_ativas)

@auth_bp.post("/mudar-status-usuario/<int:userId>")
@login_required
@role_required(PERM_MANAGEMENT)
def toggle_user_status(userId):
    # SECURITY: Verifica permissão sobre o usuário alvo
    user_alvo = Usuario.query.get_or_404(userId)
    if session.get("user_role") == ROLE_GESTOR:
        if user_alvo.papel == ROLE_ADMIN:
            return jsonify({"message": "Proibido alterar Admin"}), 403
    
    user_alvo.status = not user_alvo.status 
    try:
        db.session.commit()
        return jsonify({"message": "Status atualizado", "status": user_alvo.status}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
     
@auth_bp.post("/usuario-resetar-senha/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def reset_senha_usuario(id):
    user = Usuario.query.get_or_404(id)
    # SECURITY
    if session.get("user_role") == ROLE_GESTOR and user.papel == ROLE_ADMIN:
         return {"message": "Gestor não reseta senha de Admin"}, 403

    user.set_senha("Usuario123")
    user.primeiro_acesso = True
    db.session.commit()
    return {"message": "Sucesso"}, 200
    

@auth_bp.route("/editar-usuario/<int:id>", methods=['GET', 'POST'])
@login_required
@role_required(PERM_MANAGEMENT)
def editar_usuario(id):
    user_edit = Usuario.query.get_or_404(id)
    current_user_obj = Usuario.query.get(session.get("user_id"))

    # SECURITY Scope
    if current_user_obj.papel == ROLE_GESTOR:
        if user_edit.papel == ROLE_ADMIN:
            flash("Acesso negado.", "danger")
            return redirect(url_for('auth.lista_usuarios'))
        obras = [o for o in current_user_obj.obras_permitidas if o.status == 1]
    else:
        obras = Obra.query.filter_by(status=1).order_by(Obra.nome).all()

    return render_template("form_usuario.html", item=user_edit, categoria="usuario", obras=obras)
    
@auth_bp.get("/visualizar-usuario/<int:id>")
@login_required
@role_required(PERM_WRITE_BASIC)
def visualizar_usuario(id):
    user_view = Usuario.query.get_or_404(id)
    current_user_obj = Usuario.query.get(session.get("user_id"))
    
    # SECURITY Scope check
    if current_user_obj.papel != ROLE_ADMIN:
        # Verifica se tem obras em comum
        meus_ids = {o.id for o in current_user_obj.obras_permitidas}
        alvo_ids = {o.id for o in user_view.obras_permitidas}
        if not meus_ids.intersection(alvo_ids) and current_user_obj.id != user_view.id:
             flash("Você não tem permissão para visualizar este usuário.", "danger")
             return redirect(url_for('auth.lista_usuarios'))
        obras = [o for o in current_user_obj.obras_permitidas if o.status == 1]
    else:
        obras = Obra.query.filter_by(status=1).order_by(Obra.nome).all()
    
    view_mode = True
    supervisor_chain = get_supervisor_chain_for_user(user_view)

    nome_supervisor = None
    if getattr(user_view, 'id_supervisor', None):
        try:
            sup = Usuario.query.get(int(user_view.id_supervisor))
            nome_supervisor = sup.nome if sup else None
        except Exception: pass
    setattr(user_view, 'nome_supervisor', nome_supervisor)

    default_supervisor = None
    try:
        admin = Usuario.query.filter_by(papel='Admin').first()
        if admin: default_supervisor = {'id': admin.id, 'nome': admin.nome, 'email': admin.email}
    except Exception: pass

    return render_template(
        "form_usuario.html", 
        item=user_view, 
        categoria="usuario", 
        obras=obras, 
        view_mode=view_mode, 
        supervisor_chain=supervisor_chain, 
        default_supervisor=default_supervisor
    )

def get_supervisor_chain_for_user(user):
    chain = []
    visited = set()
    current = user
    while current and getattr(current, 'id_supervisor', None):
        try: sup_id = int(getattr(current, 'id_supervisor'))
        except Exception: break
        if sup_id in visited: break
        sup = Usuario.query.get(sup_id)
        if not sup: break
        chain.append({'id': sup.id, 'nome': sup.nome, 'email': sup.email})
        visited.add(sup.id)
        current = sup
    return chain

@auth_bp.get('/supervisores')
@login_required
def lista_supervisores():
    users = Usuario.query.order_by(Usuario.nome.asc()).all()
    result = [{'id': u.id, 'nome': u.nome, 'papel': u.papel, 'email': u.email} for u in users]
    return jsonify(result)

@auth_bp.before_app_request
def check_primeiro_acesso():
    user_id = session.get("user_id")
    if user_id:
        user = Usuario.query.get(user_id)
        if user and getattr(user, 'primeiro_acesso', False):
            rotas_permitidas = ['auth.alterar_senha_obrigatoria', 'auth.logout', 'static', 'auth.login']
            if request.endpoint not in rotas_permitidas:
                flash("Por segurança, você deve alterar sua senha no primeiro acesso.", "warning")
                return redirect(url_for('auth.alterar_senha_obrigatoria'))
        
@auth_bp.route("/alterar-senha-obrigatoria", methods=["GET", "POST"])
@login_required
def alterar_senha_obrigatoria():
    if request.method == "POST":
        nova_senha = request.form.get("nova_senha")
        confirmar_senha = request.form.get("confirmar_senha")

        if not nova_senha or not confirmar_senha:
            flash("Preencha todos os campos.", "danger")
            return render_template("alterar_senha_obrigatoria.html")

        if nova_senha != confirmar_senha:
            flash("As senhas não conferem.", "danger")
            return render_template("alterar_senha_obrigatoria.html")
            
        if len(nova_senha) < 6:
             flash("A senha deve ter no mínimo 6 caracteres.", "danger")
             return render_template("alterar_senha_obrigatoria.html")

        user = Usuario.query.get(session.get("user_id"))
        user.set_senha(nova_senha)
        user.primeiro_acesso = False 
        try:
            db.session.commit()
            flash("Senha alterada com sucesso! Bem-vindo.", "success")
            return redirect(url_for("auth.inicio"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar senha: {str(e)}", "danger")

    return render_template("alterar_senha_obrigatoria.html")

#######################################################################################################
####################################################################################################### LISTAS AUXILIARES (Clima, Equip, MaoObra, Tags)
#######################################################################################################
# RBAC: Visualizar = Todos | Criar/Editar = Admin, Gestor, Operador | Excluir = Admin, Gestor

@auth_bp.get("/lista-climas")
@login_required
def lista_climas():
    climas = AuxClima.query.filter_by(ativo=True).order_by(AuxClima.nome.asc()).all()
    return render_template("list_climas.html", opcoes=climas, categoria="clima")

@auth_bp.get('/criar-clima')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_clima():
    return render_template('form_clima.html', item=None, view_mode=False)

@auth_bp.post('/gerar-clima')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_clima():
    clima_id = request.form.get('id')
    tipo_lista = "Climas"
    nome = _normalize_option_input(request.form.get('nome', ''))
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome do clima é obrigatório.', 'danger')
        if clima_id: return redirect(url_for('auth.editar_clima', id=clima_id))
        return redirect(url_for('auth.criar_clima'))

    clima_existente = _find_duplicate_option(AuxClima, nome, tipo_lista, exclude_id=clima_id)

    if clima_existente:
        flash('Já existe um clima cadastrado com esse nome.', 'danger')
        if clima_id: return redirect(url_for('auth.editar_clima', id=clima_id))
        return redirect(url_for('auth.criar_clima'))

    if clima_id:
        clima = AuxClima.query.get(clima_id)
        if not clima: return redirect(url_for('auth.lista_climas'))
        clima.nome = nome
        clima.ativo = ativo
        db.session.add(clima)
        db.session.commit()
        return redirect(url_for('auth.lista_climas'))

    novo = AuxClima(nome=nome, tipo_lista=tipo_lista, ativo=ativo)
    db.session.add(novo)
    db.session.commit()
    return redirect(url_for('auth.lista_climas'))

@auth_bp.get('/visualizar-clima/<int:id>')
@login_required
def visualizar_clima(id):
    clima = AuxClima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=True)

@auth_bp.get('/editar-clima/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_clima(id):
    clima = AuxClima.query.get_or_404(id)
    return render_template('form_clima.html', item=clima, view_mode=False)

@auth_bp.post('/excluir-clima/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_clima(id):
    clima = AuxClima.query.get(id)
    if clima:
        db.session.delete(clima)
        db.session.commit()
    return redirect(url_for('auth.lista_climas'))

# --- EQUIPAMENTOS ---
@auth_bp.get("/lista-equipamentos")
@login_required
def lista_equipamentos():
    equipamentos = AuxEquipamentos.query.filter_by(ativo=True).order_by(AuxEquipamentos.nome.asc()).all()
    return render_template("list_equipamentos.html", opcoes=equipamentos, categoria="equipamento")

@auth_bp.get('/criar-equipamento')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_equipamento():
    return render_template('form_equipamento.html', item=None, view_mode=False)

@auth_bp.post('/gerar-equipamento')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_equipamento():
    equipamento_id = request.form.get('id')
    tipo_lista = "Equipamentos"
    nome = _normalize_option_input(request.form.get('nome', ''))
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome do equipamento é obrigatório.', 'danger')
        return redirect(url_for('auth.lista_equipamentos'))

    equipamento_existente = _find_duplicate_option(AuxEquipamentos, nome, tipo_lista, exclude_id=equipamento_id)

    if equipamento_existente:
        flash('Já existe um equipamento cadastrado com esse nome.', 'danger')
        if equipamento_id: return redirect(url_for('auth.editar_equipamento', id=equipamento_id))
        return redirect(url_for('auth.criar_equipamento'))

    if equipamento_id:
        equipamento = AuxEquipamentos.query.get(equipamento_id)
        equipamento.nome = nome
        equipamento.ativo = ativo
        db.session.add(equipamento)
    else:
        novo = AuxEquipamentos(nome=nome, tipo_lista=tipo_lista, ativo=ativo)
        db.session.add(novo)
    db.session.commit()
    return redirect(url_for('auth.lista_equipamentos'))

@auth_bp.get('/visualizar-equipamento/<int:id>')
@login_required
def visualizar_equipamento(id):
    equipamento = AuxEquipamentos.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=True)

@auth_bp.get('/editar-equipamento/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_equipamento(id):
    equipamento = AuxEquipamentos.query.get_or_404(id)
    return render_template('form_equipamento.html', item=equipamento, view_mode=False)

@auth_bp.post('/excluir-equipamento/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_equipamento(id):
    equipamento = AuxEquipamentos.query.get(id)
    if equipamento:
        db.session.delete(equipamento)
        db.session.commit()
    return redirect(url_for('auth.lista_equipamentos'))

# --- TAGS ---
@auth_bp.get("/lista-tags-ocorrencias")
@login_required
def lista_tags_ocorrencias():
    tagsOcorrencias = AuxTagOcorrencia.query.filter_by(ativo=True).order_by(AuxTagOcorrencia.nome.asc()).all()
    return render_template("list_tags_ocorrencias.html", opcoes=tagsOcorrencias, categoria="tagsOcorrencias")

@auth_bp.get('/criar-tags-ocorrencias')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_tags_ocorrencias():
    return render_template('form_tags_ocorrencias.html', item=None, view_mode=False)

@auth_bp.post('/gerar-tags-ocorrencias')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_tags_ocorrencias():
    tag_id = request.form.get('id')
    nome = _normalize_option_input(request.form.get('nome', ''))
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome da tag é obrigatório.', 'danger')
        return redirect(url_for('auth.lista_tags_ocorrencias'))

    tag_existente = _find_duplicate_option(AuxTagOcorrencia, nome, "Tags Ocorrencias", exclude_id=tag_id)

    if tag_existente:
        flash('Já existe uma tag de ocorrência cadastrada com esse nome.', 'danger')
        if tag_id: return redirect(url_for('auth.editar_tags_ocorrencias', id=tag_id))
        return redirect(url_for('auth.criar_tags_ocorrencias'))

    if tag_id:
        tag = AuxTagOcorrencia.query.get(tag_id)
        tag.nome = nome
        tag.ativo = ativo
        db.session.add(tag)
    else:
        db.session.add(AuxTagOcorrencia(nome=nome, tipo_lista="Tags Ocorrencias", ativo=ativo))
    db.session.commit()
    return redirect(url_for('auth.lista_tags_ocorrencias'))

@auth_bp.get('/visualizar-tags-ocorrencias/<int:id>')
@login_required
def visualizar_tags_ocorrencias(id):
    tag = AuxTagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag, view_mode=True)

@auth_bp.get('/editar-tags-ocorrencias/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_tags_ocorrencias(id):
    tag = AuxTagOcorrencia.query.get_or_404(id)
    return render_template('form_tags_ocorrencias.html', item=tag, view_mode=False)

@auth_bp.post('/excluir-tags-ocorrencias/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_tags_ocorrencias(id):
    tag = AuxTagOcorrencia.query.get(id)
    if tag:
        db.session.delete(tag)
        db.session.commit()
    return redirect(url_for('auth.lista_tags_ocorrencias'))

# --- MAO DE OBRA ---
@auth_bp.get("/lista-mao-obra")
@login_required
def lista_mao_obra():
    mao_obra = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    return render_template("list_mao_obra.html", opcoes=mao_obra, categoria="mao_obra")

@auth_bp.get('/criar-mao-obra')
@login_required
@role_required(PERM_WRITE_BASIC)
def criar_mao_obra():
    return render_template('form_mao_obra.html', item=None, view_mode=False)

@auth_bp.post('/gerar-mao-obra')
@login_required
@role_required(PERM_WRITE_BASIC)
def gerar_mao_obra():
    mo_id = request.form.get('id')
    nome = _normalize_option_input(request.form.get('nome', ''))
    tipo = _normalize_option_input(request.form.get('tipo', '')) or None
    ativo = request.form.get('ativo') == '1'
    if not nome:
        flash('Nome da mão de obra é obrigatório.', 'danger')
        return redirect(url_for('auth.lista_mao_obra'))

    mo_existente = _find_duplicate_option(AuxFuncoes, nome, "Mao de Obra", exclude_id=mo_id, tipo=tipo)

    if mo_existente:
        flash('Já existe uma mão de obra cadastrada com esse nome e tipo.', 'danger')
        if mo_id: return redirect(url_for('auth.editar_mao_obra', id=mo_id))
        return redirect(url_for('auth.criar_mao_obra'))

    if mo_id:
        mo = AuxFuncoes.query.get(mo_id)
        mo.nome = nome
        mo.tipo = tipo
        mo.ativo = ativo
        db.session.add(mo)
    else:
        db.session.add(AuxFuncoes(nome=nome, tipo_lista="Mao de Obra", tipo=tipo, ativo=ativo))
    db.session.commit()
    return redirect(url_for('auth.lista_mao_obra'))

@auth_bp.get('/visualizar-mao-obra/<int:id>')
@login_required
def visualizar_mao_obra(id):
    mo = AuxFuncoes.query.get_or_404(id)
    return render_template('form_mao_obra.html', item=mo, view_mode=True)

@auth_bp.get('/editar-mao-obra/<int:id>')
@login_required
@role_required(PERM_WRITE_BASIC)
def editar_mao_obra(id):
    mo = AuxFuncoes.query.get_or_404(id)
    return render_template('form_mao_obra.html', item=mo, view_mode=False)

@auth_bp.post('/excluir-mao-obra/<int:id>')
@login_required
@role_required(PERM_MANAGEMENT)
def excluir_mao_obra(id):
    mo = AuxFuncoes.query.get(id)
    if mo:
        db.session.delete(mo)
        db.session.commit()
    return redirect(url_for('auth.lista_mao_obra'))

#######################################################################################################
####################################################################################################### OBRAS
#######################################################################################################

@auth_bp.get("/lista-obras")
@login_required
def lista_obras():
    # SCOPING:
    user = Usuario.query.get(session.get("user_id"))
    query = Obra.query.order_by(Obra.id.asc())
    
    if user.papel != ROLE_ADMIN:
        meus_ids = [o.id for o in Obra.query.filter_by(empresa_id=session.get('empresa_id')).all()]
        query = query.filter(Obra.id.in_(meus_ids))
        
    resultados = query.all()
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
            'status': obra_obj.status,
            'frentes_trabalho': obra_obj.frentes_trabalho
        }
        obras_formatadas.append(obra_dict)
    
    return render_template("list_obras.html", opcoes=obras_formatadas, categoria="obra")

@auth_bp.get("/criar-obra")
@login_required
@role_required(PERM_MANAGEMENT) # Apenas Admin e Gestor
def criar_obra():
    usuarios = Usuario.query.filter_by(status=1).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    return render_template("form_obra.html", item=None, usuarios=usuarios, mao_de_obra_options=mao_de_obra_options, equipe_obra=[])

@auth_bp.post("/mudar-status-obras/<int:obraid>")
@login_required
@role_required(PERM_MANAGEMENT)
def toggle_user_obras(obraid):
    # Security scope check
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and obraid not in scope_ids:
        return {"message": "Forbidden"}, 403

    obra = Obra.query.get_or_404(obraid)
    obra.status = not obra.status 
    try:
        db.session.commit()
        return {"message": "Status atualizado com sucesso"}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"Erro ao atualizar: {str(e)}"}, 500
    
@auth_bp.route('/gerar-obra', methods=['POST'])
@login_required
@role_required(PERM_MANAGEMENT)
def gerar_obra():
    obra_id = request.form.get("id")
    if obra_id:
        # Security scope
        scope_ids = get_user_scope_ids()
        if scope_ids is not None and int(obra_id) not in scope_ids:
             flash("Sem permissão para editar esta obra", "danger")
             return redirect(url_for('auth.lista_obras'))

    cnpj = request.form.get('cnpj')
    obra_existente = Obra.query.filter_by(cnpj=cnpj).first()
    if obra_existente:
        if not obra_id or str(obra_existente.id) != str(obra_id):
            flash(f"Erro: O CNPJ {cnpj} já está cadastrado.", "danger")
            return redirect(url_for('auth.lista_obras'))

    nome = request.form.get('nome')
    contratante = request.form.get('contratante')
    contrato = request.form.get('contrato')
    criado_por = request.form.get('criado_por')
    inicio_str = request.form.get('inicio')
    termino_str = request.form.get('termino')
    horario_entrada_str = request.form.get('horario_entrada')
    horario_saida_str = request.form.get('horario_saida')
    cep = request.form.get('cep')
    endereco = request.form.get('endereco')
    numero = request.form.get('numero')
    complemento = request.form.get('complemento')
    bairro = request.form.get('bairro')
    cidade = request.form.get('cidade')
    estado = request.form.get('estado')
    status = 1 if request.form.get('status') == 'on' else 0
    frentes_payload = request.form.get('frentes_json')
    equipe_payload = request.form.get('equipe_obra_json')

    try:
        inicio = datetime.strptime(inicio_str, '%Y-%m-%d').date() if inicio_str else None
        termino = datetime.strptime(termino_str, '%Y-%m-%d').date() if termino_str else None
        horario_entrada = datetime.strptime(horario_entrada_str, '%H:%M').time() if horario_entrada_str else None
        horario_saida = datetime.strptime(horario_saida_str, '%H:%M').time() if horario_saida_str else None

        if obra_id:
            obra = Obra.query.get(obra_id)
            obra.nome = nome
            obra.cnpj = cnpj
            obra.contratante = contratante
            obra.contrato = contrato
            obra.criado_por = criado_por if criado_por else None
            obra.data_inicio = inicio
            obra.data_fim = termino
            obra.horario_entrada = horario_entrada
            obra.horario_saida = horario_saida
            obra.cep = cep
            obra.endereco = endereco
            obra.numero = numero
            obra.complemento = complemento
            obra.bairro = bairro
            obra.cidade = cidade
            obra.estado = estado
            obra.status = status
            flash("Obra atualizada com sucesso!", "success")
        else:
            obra = Obra(
                nome=nome, cnpj=cnpj, contratante=contratante, contrato=contrato,
                criado_por=criado_por if criado_por else None,
                inicio=inicio, termino=termino,
                horario_entrada=horario_entrada, horario_saida=horario_saida,
                cep=cep, endereco=endereco, numero=numero, complemento=complemento,
                bairro=bairro, cidade=cidade, estado=estado, status=status
            )
            db.session.add(obra)
            db.session.flush() 
            flash("Obra cadastrada com sucesso!", "success")

            # Se quem criou foi um Gestor, adiciona automaticamente permissão pra ele
            current_user_obj = Usuario.query.get(session.get("user_id"))
            if current_user_obj.papel == ROLE_GESTOR:
                current_user_obj.obras_permitidas.append(obra)

        if frentes_payload:
            data = json.loads(frentes_payload)
            for f_id in data.get('removidas', []):
                if f_id: FrenteTrabalho.query.filter_by(frente_trabalho_id=f_id, obra_id=obra.id).delete()
            
            for f_nova in data.get('novas', []):
                nova_frente = FrenteTrabalho(
                    obra_id=obra.id,
                    nome_frente=f_nova['nome_frente'],
                    criado_por=f_nova['criado_por'] if f_nova['criado_por'] else None,
                    unidade=f_nova.get('unidade'),
                    qtd_planejada=float(f_nova.get('qtd_planejada')) if f_nova.get('qtd_planejada') else 0,
                    data_inicio=datetime.strptime(f_nova.get('data_inicio'), '%Y-%m-%d').date() if f_nova.get('data_inicio') else None,
                    data_planejada=datetime.strptime(f_nova.get('data_planejada'), '%Y-%m-%d').date() if f_nova.get('data_planejada') else None
                )
                db.session.add(nova_frente)

            for f_edit in data.get('editadas', []):
                frente_existente = FrenteTrabalho.query.get(f_edit['frente_trabalho_id'])
                if frente_existente and frente_existente.obra_id == obra.id:
                    frente_existente.nome_frente = f_edit['nome_frente']
                    frente_existente.criado_por = f_edit['criado_por'] if f_edit['criado_por'] else None
                    frente_existente.unidade = f_edit.get('unidade')
                    frente_existente.qtd_planejada = float(f_edit.get('qtd_planejada')) if f_edit.get('qtd_planejada') else 0
                    frente_existente.data_inicio = datetime.strptime(f_edit.get('data_inicio'), '%Y-%m-%d').date() if f_edit.get('data_inicio') else None
                    frente_existente.data_planejada = datetime.strptime(f_edit.get('data_planejada'), '%Y-%m-%d').date() if f_edit.get('data_planejada') else None

        if equipe_payload is not None:
            EquipeObraAuxFuncoes.query.filter_by(obra_id=obra.id).delete()
            equipe_rows = json.loads(equipe_payload) if equipe_payload else []
            equipe_agrupada = {}
            for equipe_item in equipe_rows:
                mo_id = equipe_item.get('id_lista_opcoes')
                quantidade = equipe_item.get('quantidade_mao_obra')
                try:
                    mo_id = int(mo_id)
                    quantidade = int(quantidade)
                except (TypeError, ValueError):
                    continue

                if quantidade <= 0:
                    continue

                equipe_agrupada[mo_id] = equipe_agrupada.get(mo_id, 0) + quantidade

            for mo_id, quantidade in equipe_agrupada.items():
                db.session.add(
                    EquipeObraAuxFuncoes(
                        obra_id=obra.id,
                        id_lista_opcoes=mo_id,
                        quantidade_mao_obra=quantidade,
                    )
                )

        db.session.commit()
        return redirect(url_for('auth.lista_obras'))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar a solicitação: {str(e)}", "danger")
        return redirect(url_for('auth.lista_obras'))
    
@auth_bp.get("/editar-obra/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def editar_obra(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        abort(403)

    obra = Obra.query.get_or_404(id)
    frentes = FrenteTrabalho.query.filter_by(obra_id=id).all()
    usuarios = Usuario.query.filter_by(status=1).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    equipe_obra = _get_equipe_obra_payload(id)
    return render_template("form_obra.html", item=obra, frentes=frentes, usuarios=usuarios, mao_de_obra_options=mao_de_obra_options, equipe_obra=equipe_obra)

@auth_bp.get("/visualizar-obra/<int:id>")
@login_required
def visualizar_obra(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        flash("Acesso restrito.", "danger")
        return redirect(url_for('auth.lista_obras'))

    item = Obra.query.get_or_404(id) 
    usuarios = Usuario.query.filter_by(status=1).all()
    frentes = FrenteTrabalho.query.filter_by(obra_id=id).all()
    usuario = Usuario.query.order_by(Usuario.nome).all()
    mao_de_obra_options = AuxFuncoes.query.filter_by(ativo=True).order_by(AuxFuncoes.nome.asc()).all()
    equipe_obra = _get_equipe_obra_payload(id)
    
    return render_template(
        "form_obra.html", 
        item=item, 
        view_mode=True, 
        categoria="obra",
        frentes=frentes,
        usuario=usuario,
        usuarios=usuarios,
        mao_de_obra_options=mao_de_obra_options,
        equipe_obra=equipe_obra
    )

@auth_bp.post("/obra/toggle-status/<int:id>")
@login_required
@role_required(PERM_MANAGEMENT)
def toggle_obra_status(id):
    # Security scope
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and id not in scope_ids:
        return '', 403

    obra = Obra.query.get_or_404(id)
    if obra.status == 1: obra.status = 0
    else: obra.status = 1
    try:
        db.session.commit()
        return '', 200 
    except Exception:
        db.session.rollback()
        return '', 500
      
#######################################################################################################
####################################################################################################### MEU PERFIL (Todos os users)
#######################################################################################################

@auth_bp.get("/meu-perfil")
@login_required
def meu_perfil():
    user = Usuario.query.get(session.get("user_id"))
    return render_template("configuracoes_perfil.html", current_user=user)

@auth_bp.post("/atualizar-meu-perfil")
@login_required
def atualizar_perfil():
    user = Usuario.query.get(session.get("user_id"))
    nome = request.form.get("nome")
    telefone = request.form.get("telefone") 
    departamento = request.form.get("departamento") 
    
    if user:
        user.nome = nome
        user.departamento = departamento
        if hasattr(user, 'telefone'): user.telefone = telefone
        try:
            db.session.commit()
            session["user_name"] = user.nome
            flash("Perfil atualizado com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
    return redirect(url_for("auth.meu_perfil"))

@auth_bp.post("/alterar-minha-senha")
@login_required
def alterar_minha_senha():
    senha_atual = request.form.get("senha_atual")
    nova_senha = request.form.get("nova_senha")
    confirmar_senha = request.form.get("confirmar_senha")
    
    if nova_senha != confirmar_senha:
        flash("A confirmação da nova senha não confere.", "danger")
        return redirect(url_for("auth.meu_perfil"))
        
    user = Usuario.query.get(session.get("user_id"))
    if not user or not check_password_hash(user.senha, senha_atual):
        flash("A senha atual está incorreta.", "danger")
        return redirect(url_for("auth.meu_perfil"))
        
    try:
        user.set_senha(nova_senha)
        db.session.commit()
        flash("Senha alterada com sucesso! Use a nova senha no próximo login.", "success")
    except Exception:
        db.session.rollback()
        flash("Erro ao alterar senha.", "danger")
    return redirect(url_for("auth.meu_perfil"))

#######################################################################################################
####################################################################################################### EASTER EGG
#######################################################################################################

@auth_bp.get("/dev-access")
def creator_secret():
    perfil = {
        "nome": "Edson Rodrigues",
        "role": "Fullstack Developer & Tech Planner",
        "stack": ["Python", "Microsoft 365", "SQL", "JavaScript", "Java", "HTML/CSS"],
        "projetos": ["Sistema RDO", "Automação de Relatórios", "Dashboard Interativo"],
        "local": "São Paulo, SP",
        "status": "Construindo o futuro, linha por linha.",
        "links": {
            "linkedin": "https://www.linkedin.com/in/edson-rodrigues-5a1a46345/",
            "github": "https://github.com/werneckx", 
            "instagram": "https://instagram.com/werneckx", 
            "email": "mailto:er4273270@gmail.com"
        }
    }
    return render_template("criador.html", dev=perfil)

#######################################################################################################
####################################################################################################### VALIDAÇÃO PUBLICA (PÚBLICO)
#######################################################################################################

def normalizar_texto(texto):
    if not texto: return ""
    nfkd_form = unicodedata.normalize('NFKD', str(texto))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()

def extrair_dados_pdf_fitz(pdf_bytes):
    if not fitz: return []
    dados = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            palavras = page.get_text("words")
            for p in palavras:
                text_norm = normalizar_texto(p[4])
                if not text_norm: continue
                dados.append({
                    'text': text_norm,
                    'text_raw': p[4],
                    'page': i,
                    'rect': fitz.Rect(p[0], p[1], p[2], p[3])
                })
    except Exception as e: print(f"Erro extração fitz: {e}")
    return dados

def gerar_diff_visual(dados_orig, dados_up):
    diff_cards = []
    rects_to_highlight_orig = []
    rects_to_highlight_up = []
    
    textos_orig = [d['text'] for d in dados_orig]
    textos_up = [d['text'] for d in dados_up]
    
    matcher = difflib.SequenceMatcher(None, textos_orig, textos_up)
    
    ignore_list = ["criado:", "modificado:", "impressão:", "gerado", "id:", "hash:", "ip:", "rev."]
    def eh_ignoravel(t): return any(ign in t.lower() for ign in ignore_list)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal': continue
        frag_orig_list = [dados_orig[x]['text_raw'] for x in range(i1, i2)]
        frag_up_list = [dados_up[x]['text_raw'] for x in range(j1, j2)]
        frag_orig_str = " ".join(frag_orig_list)
        frag_up_str = " ".join(frag_up_list)
        if eh_ignoravel(frag_orig_str) or eh_ignoravel(frag_up_str): continue
        if frag_orig_str.replace(" ", "") == frag_up_str.replace(" ", ""): continue
        
        if tag == 'replace':
            diff_cards.append({'tipo': 'alteracao', 'original': frag_orig_str, 'enviado': frag_up_str})
            rects_to_highlight_orig.extend([d for d in dados_orig[i1:i2]])
            rects_to_highlight_up.extend([d for d in dados_up[j1:j2]])
        elif tag == 'delete':
            diff_cards.append({'tipo': 'remocao', 'original': frag_orig_str, 'enviado': ""})
            rects_to_highlight_orig.extend([d for d in dados_orig[i1:i2]])
        elif tag == 'insert':
            diff_cards.append({'tipo': 'adicao', 'original': "", 'enviado': frag_up_str})
            rects_to_highlight_up.extend([d for d in dados_up[j1:j2]])
            
    return diff_cards, rects_to_highlight_orig, rects_to_highlight_up

def aplicar_highlights(pdf_bytes, lista_dados, color):
    if not fitz or not lista_dados: return pdf_bytes
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        por_pagina = {}
        for item in lista_dados:
            p = item['page']
            if p not in por_pagina: por_pagina[p] = []
            por_pagina[p].append(item['rect'])
        for page_idx, rects in por_pagina.items():
            if page_idx < len(doc):
                page = doc[page_idx]
                for r in rects:
                    annot = page.add_highlight_annot(r)
                    annot.set_colors(stroke=color)
                    annot.update()
        output = BytesIO()
        doc.save(output)
        return output.getvalue()
    except Exception: return pdf_bytes

@auth_bp.route("/validar-documento", methods=["GET", "POST"])
def validar_documento_publico():
    from app.models.rdo import RDO, RDOAprovacao
    try:
        from pypdf import PdfReader
        from io import BytesIO
    except ImportError: PdfReader = None
    
    resultado = None
    erro = None
    hash_buscado = ""
    status_auditoria = "pendente"
    diff_data = [] 
    pdf_original_b64 = None
    pdf_enviado_b64 = None
    texto_pdf_enviado = ""
    bytes_original = None
    bytes_enviado = None

    if request.method == 'POST':
        if 'pdf_file' in request.files and request.files['pdf_file'].filename != '':
            if PdfReader is None:
                 erro = "Erro interno: Biblioteca 'pypdf' não instalada."
            else:
                try:
                    arquivo_pdf = request.files['pdf_file']
                    bytes_enviado = arquivo_pdf.read()
                    stream_enviado = BytesIO(bytes_enviado)
                    leitor = PdfReader(stream_enviado)
                    for pagina in leitor.pages: texto_pdf_enviado += pagina.extract_text() + "\n"
                    texto_norm = normalizar_texto(texto_pdf_enviado)
                    match = re.search(r"id:\s*([a-fa-f0-9]{64})", texto_norm)
                    if match: hash_buscado = match.group(1)
                    else:
                        match_solto = re.search(r"([a-fa-f0-9]{64})", texto_norm)
                        if match_solto: hash_buscado = match_solto.group(1)
                        else: erro = "Código de autenticidade (Hash) não encontrado no arquivo."
                    pdf_enviado_b64 = base64.b64encode(bytes_enviado).decode('utf-8')
                except Exception as e: erro = f"Erro ao processar arquivo: {str(e)}"

    if hash_buscado:
        assinatura = RDOAprovacao.query.filter_by(hash=hash_buscado).first()
        if assinatura:
            if assinatura.status == 'APROVADO':
                rdo = assinatura.rdo
                if texto_pdf_enviado:
                    try:
                        bytes_original = render_rdo_pdf(rdo.id)
                        if fitz:
                            dados_orig = extrair_dados_pdf_fitz(bytes_original)
                            dados_up = extrair_dados_pdf_fitz(bytes_enviado)
                            diff_data, rects_orig, rects_up = gerar_diff_visual(dados_orig, dados_up)
                            if rects_orig: bytes_original = aplicar_highlights(bytes_original, rects_orig, (1, 0, 0))
                            if rects_up: bytes_enviado = aplicar_highlights(bytes_enviado, rects_up, (0, 1, 0))
                        
                        status_auditoria = "aprovado" if len(diff_data) == 0 else "alerta"
                        pdf_original_b64 = base64.b64encode(bytes_original).decode('utf-8')
                        pdf_enviado_b64 = base64.b64encode(bytes_enviado).decode('utf-8')
                    except Exception as e:
                        print(f"Erro Auditoria: {e}")
                        status_auditoria = "erro"
                
                resultado = {
                    "valido": True,
                    "rdo_id": rdo.id_sequencial,
                    "revisao": rdo.id_revisao,
                    "obra": rdo.obra.nome,
                    "data_rdo": rdo.data,
                    "assinante_nome": assinatura.aprovador.nome,
                    "assinante_papel": assinatura.aprovador.papel,
                    "data_assinatura": assinatura.data_aprovacao,
                    "hash_completo": assinatura.hash,
                    "status_auditoria": status_auditoria,
                    "diff_data": diff_data,
                    "pdf_original_b64": pdf_original_b64,
                    "pdf_enviado_b64": pdf_enviado_b64
                }
            else: erro = "Este documento foi invalidado no sistema."
        else: erro = "Código de autenticidade (Hash) não encontrado na base de dados."

    return render_template("public_validacao.html", resultado=resultado, erro=erro, hash_buscado=hash_buscado)
