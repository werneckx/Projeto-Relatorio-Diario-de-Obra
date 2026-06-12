from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive

class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)

    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200), nullable=True)
    cnpj = db.Column(db.String(14), nullable=False)

    logradouro = db.Column(db.String(200), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True, index=True)
    estado = db.Column(db.String(2), nullable=True, index=True)
    cep = db.Column(db.String(10), nullable=True)

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

    def __init__(self, *args, **kwargs):
        """
        Compatibilidade retroativa para chamadas que ainda usam `nome=...`.

        Alguns testes/camadas antigas podem instanciar:
            Cliente(nome="X", ...)
        enquanto o model atual espera:
            Cliente(razao_social="X", ...)

        Esta adaptação mantém a estrutura do banco intacta.
        """
        nome = kwargs.pop("nome", None)
        if nome and "razao_social" not in kwargs:
            kwargs["razao_social"] = nome
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f'<Cliente {self.id}: {self.razao_social}>'

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
