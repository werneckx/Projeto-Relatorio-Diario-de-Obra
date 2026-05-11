from datetime import datetime
from app import db


class Arquivo(db.Model):
    __tablename__ = "arquivos"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=True, index=True)
    entidade = db.Column(db.String(80), nullable=True)
    entidade_id = db.Column(db.Integer, nullable=True)
    categoria = db.Column(
        db.Enum('PDF', 'IMAGEM', 'ART', 'CONTRATO', 'ANEXO', 'DOCUMENTO', 'OUTRO'),
        nullable=False,
        default='ANEXO',
    )
    nome_original = db.Column(db.String(255), nullable=False)
    nome_armazenado = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    tamanho_bytes = db.Column(db.BigInteger, nullable=True)
    storage_provider = db.Column(
        db.Enum('LOCAL', 'S3', 'AZURE', 'MINIO'),
        nullable=False,
        default='LOCAL',
    )
    storage_path = db.Column(db.String(500), nullable=False)
    hash_arquivo = db.Column(db.String(255), nullable=True)
    publico = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    modificado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship('Empresa', backref='arquivos')
    obra = db.relationship('Obra', backref='arquivos')
    rdo = db.relationship('RDO', backref='arquivos')
    criador = db.relationship('Usuario', foreign_keys=[criado_por])
    modificador = db.relationship('Usuario', foreign_keys=[modificado_por])

    def __repr__(self):
        return f'<Arquivo {self.nome_original}>'
