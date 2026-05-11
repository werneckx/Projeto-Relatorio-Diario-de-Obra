from datetime import datetime
from app import db


class SessaoUsuario(db.Model):
    __tablename__ = "sessoes_usuario"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(255), nullable=False, unique=True)
    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    iniciada_em = db.Column(db.DateTime, default=datetime.utcnow)
    expira_em = db.Column(db.DateTime, nullable=False, index=True)
    encerrada_em = db.Column(db.DateTime, nullable=True)
    encerrada_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    motivo_encerramento = db.Column(db.String(100), nullable=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True)

    empresa = db.relationship('Empresa', backref='sessoes_usuario')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id], backref='sessoes')
    usuario_encerramento = db.relationship('Usuario', foreign_keys=[encerrada_por])

    def encerrar(self, usuario_id=None, motivo=None):
        self.ativa = False
        self.encerrada_em = datetime.utcnow()
        self.encerrada_por = usuario_id
        self.motivo_encerramento = motivo

    def __repr__(self):
        return f'<SessaoUsuario Usuario:{self.usuario_id} Ativa:{self.ativa}>'


class AcessoLog(db.Model):
    __tablename__ = "acesso_log"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, index=True)
    email = db.Column(db.String(150), nullable=True, index=True)
    acao = db.Column(
        db.Enum(
            'LOGIN_SUCESSO',
            'LOGIN_FALHA',
            'LOGOUT',
            'LOGOUT_REMOTO',
            'SESSAO_EXPIRADA',
            'SENHA_REDEFINIDA',
        ),
        nullable=False,
    )
    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    detalhes = db.Column(db.JSON, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    empresa = db.relationship('Empresa', backref='acessos_log')
    usuario = db.relationship('Usuario', backref='acessos_log')

    def __repr__(self):
        return f'<AcessoLog {self.acao} {self.email or self.usuario_id}>'
