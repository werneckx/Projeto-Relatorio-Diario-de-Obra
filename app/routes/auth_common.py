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

def _get_equipe_obra_payload(obra_id):
    # O schema atual não define o modelo de equipe de obra que existia em versões anteriores.
    # Mantemos a interface do formulário, mas não tentamos carregar ou gravar dados inexistentes.
    return []


__all__ = [name for name in globals() if not name.startswith("__")]
