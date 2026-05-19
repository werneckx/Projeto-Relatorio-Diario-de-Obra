from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive


class Fornecedor(db.Model):
    __tablename__ = "fornecedores"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    nome = db.Column(db.String(150), nullable=False)
    cnpj = db.Column(db.String(20), nullable=True)
    endereco = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    empresa = db.relationship('Empresa', backref='fornecedores')

    # Colaboradores vinculados a este fornecedor
    colaboradores = db.relationship('Colaborador', backref='fornecedor', lazy='dynamic')

    def __repr__(self):
        return f'<Fornecedor {self.nome}>'

    def to_dict(self):
        return {
            'id': self.id,
            'empresa_id': self.empresa_id,
            'nome': self.nome,
            'cnpj': self.cnpj or '',
            'endereco': self.endereco or '',
            'ativo': self.ativo,
        }
