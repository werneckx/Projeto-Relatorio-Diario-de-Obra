from datetime import datetime
from app import db 

class Empresa(db.Model):
    __tablename__ = "empresa"

    id = db.Column(db.Integer, primary_key=True)
    nome_empresa = db.Column(db.String(255), nullable=False)
    logo_empresa = db.Column(db.String(255), nullable=True)  # Caminho do arquivo de logo
    icone_empresa = db.Column(db.String(255), nullable=True)  # Caminho do arquivo de ícone