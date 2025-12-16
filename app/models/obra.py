from app import db
from datetime import date

class Obra(db.Model):
    __tablename__ = "obra"

    id = db.Column(db.Integer, primary_key=True)
    id_matriz = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    nome = db.Column(db.String(120), nullable=False)
    cnpj = db.Column(db.String(14), unique=True, nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    numero = db.Column(db.String(10), nullable=False)
    complemento = db.Column(db.String(50))
    bairro = db.Column(db.String(120), nullable=False)
    cidade = db.Column(db.String(120), nullable=False)
    estado = db.Column(db.String(2), nullable=False)
    cep = db.Column(db.String(8), nullable=False)
    inicio = db.Column(db.Date, nullable=False)
    termino = db.Column(db.Date, nullable=False)
    status = db.Column(db.Integer)
    
    def __repr__(self):
        return f'<Obra {self.id}: {self.nome}>'
    
    