from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive

class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)

    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200), nullable=True)
    cnpj = db.Column(db.String(18), nullable=False)

    contato_nome = db.Column(db.String(150), nullable=True)
    contato_email = db.Column(db.String(150), nullable=True)
    contato_telefone = db.Column(db.String(30), nullable=True)

    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    # Relacionamentos
    empresa = db.relationship('Empresa', backref='clientes')
    obras = db.relationship("Obra", back_populates="cliente")

    def __repr__(self):
        return f'<Cliente {self.id}: {self.razao_social}>'
