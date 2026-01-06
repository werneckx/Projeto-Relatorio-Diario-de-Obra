from app import db
from datetime import date

class Obra(db.Model):
    __tablename__ = "obra"

    id = db.Column(db.Integer, primary_key=True)
    id_matriz = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=True)
    nome = db.Column(db.String(120), nullable=False)
    contratante = db.Column(db.String(255), nullable=False)
    contrato = db.Column(db.String(50), unique=True, nullable=False)
    id_responsavel = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
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
    
    # Relacionamento para facilitar a exibição do nome do responsável
    responsavel = db.relationship('Usuario', foreign_keys=[id_responsavel])
    
    def __repr__(self):
        return f'<Obra {self.id}: {self.nome}>'
    
class Frente_Trabalho(db.Model):
    __tablename__ = "frente_trabalho"
    
    id_frente_trabalho = db.Column(db.Integer, primary_key=True)
    # Garanta que a FK aponte para 'obra.id' (nome da tabela e coluna)
    id_obra = db.Column(db.Integer, db.ForeignKey('obra.id'), nullable=False)
    # AJUSTE: nullable=True para permitir criar a frente sem atribuir um responsável de imediato
    # Verifique se o __tablename__ do seu modelo de usuário é realmente 'usuario'
    id_responsavel = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    nome_frente = db.Column(db.String(120), nullable=False)
    
    responsavel = db.relationship('Usuario', backref='frentes')

    def __repr__(self):
        return f'<Frente {self.nome_frente}>'