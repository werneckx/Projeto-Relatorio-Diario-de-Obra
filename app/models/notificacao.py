from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive


class Notificacao(db.Model):
    __tablename__ = "notificacoes"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=True, index=True)
    tipo = db.Column(
        db.Enum(
            'APROVACAO_PENDENTE',
            'NOVO_RDO',
            'ALERTA',
            'REJEICAO',
            'AVISO_OPERACIONAL',
            'SISTEMA',
        ),
        nullable=False,
    )
    titulo = db.Column(db.String(150), nullable=False)
    mensagem = db.Column(db.Text, nullable=True)
    link = db.Column(db.String(255), nullable=True)
    lida = db.Column(db.Boolean, nullable=False, default=False)
    lida_em = db.Column(db.DateTime, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)

    empresa = db.relationship('Empresa', backref='notificacoes')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='notificacoes')
    obra = db.relationship('Obra', backref='notificacoes')
    rdo = db.relationship('RDO', backref='notificacoes')
    criador = db.relationship('Usuario', foreign_keys=[criado_por])

    def marcar_como_lida(self):
        self.lida = True
        self.lida_em = utcnow_naive()

    def __repr__(self):
        return f'<Notificacao {self.tipo}: {self.titulo}>'
