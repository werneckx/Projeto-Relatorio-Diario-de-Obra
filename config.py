import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente a partir do arquivo .env
load_dotenv()

class Config:
    # SECRET_KEY deve vir do ambiente para produção
    SECRET_KEY = os.environ.get("SECRET_KEY", "MINHA_CHAVE_SECRETA_FIXA_123456789")

    # Configuração do banco
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "dbrdo")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", 3306)

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Diretórios padrão
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    RDO_GERADOS_DIR = os.path.join(BASE_DIR, "rdo_gerados")
    STATIC_DIR = os.path.join(BASE_DIR, "static")

    # Caminho do wkhtmltopdf (Windows)
    WKHTMLTOPDF_CMD = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
