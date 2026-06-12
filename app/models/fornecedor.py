from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive


class Fornecedor(db.Model):
    __tablename__ = "fornecedores"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    nome = db.Column(db.String(150), nullable=False)
    cnpj = db.Column(db.String(14), nullable=True, index=True)
    logradouro = db.Column(db.String(200), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True, index=True)
    estado = db.Column(db.String(2), nullable=True, index=True)
    cep = db.Column(db.String(10), nullable=True)
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

    @property
    def endereco(self):
        partes = [self.logradouro]
        if self.numero:
            partes.append(f"nº {self.numero}")
        if self.complemento:
            partes.append(self.complemento)
        if self.bairro:
            partes.append(self.bairro)
        cidade_uf = "/".join(filter(None, [self.cidade, self.estado]))
        if cidade_uf:
            partes.append(cidade_uf)
        if self.cep:
            partes.append(f"CEP {self.cep}")
        return ", ".join([parte for parte in partes if parte])

    @endereco.setter
    def endereco(self, value):
        if value and not self.logradouro:
            self.logradouro = value

    def to_dict(self):
        return {
            'id': self.id,
            'empresa_id': self.empresa_id,
            'nome': self.nome,
            'cnpj': self.cnpj or '',
            'endereco': self.endereco or '',
            'logradouro': self.logradouro or '',
            'numero': self.numero or '',
            'complemento': self.complemento or '',
            'bairro': self.bairro or '',
            'cidade': self.cidade or '',
            'estado': self.estado or '',
            'cep': self.cep or '',
            'ativo': self.ativo,
        }
