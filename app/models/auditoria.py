from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive

class AuditoriaLog(db.Model):
    __tablename__ = "auditoria_log"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, index=True)
    colaborador_id = db.Column(db.Integer, db.ForeignKey('colaboradores.id'), nullable=True, index=True)

    acao = db.Column(db.String(50), nullable=False)
    entidade = db.Column(db.String(50), nullable=False)
    entidade_id = db.Column(db.Integer, nullable=True, index=True)

    dados_antes = db.Column(db.JSON, nullable=True)
    dados_depois = db.Column(db.JSON, nullable=True)

    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=utcnow_naive, index=True)

    # Relacionamentos
    empresa = db.relationship('Empresa')
    usuario = db.relationship('Usuario')
    colaborador = db.relationship('Colaborador')

    def __repr__(self):
        return f'<AuditoriaLog {self.acao} em {self.entidade}:{self.entidade_id}>'
