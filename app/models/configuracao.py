import json
from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive

class ConfigDefinicao(db.Model):
    __tablename__ = "config_definicoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chave = db.Column(db.String(100), nullable=False, unique=True, index=True)
    descricao = db.Column(db.Text, nullable=True)
    tipo = db.Column(db.Enum('BOOLEAN', 'STRING', 'INT', 'JSON'), nullable=False)
    valor_padrao = db.Column(db.Text, nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)

    def cast_value(self, raw_value):
        if raw_value is None:
            return self.valor_padrao
        
        # Normalize and cast according to type, but never raise
        if raw_value is None:
            return self.valor_padrao

        # BOOLEAN
        if self.tipo == 'BOOLEAN':
            v = str(raw_value).strip().lower()
            if v in ('1', 'true', 't', 'y', 'yes'):
                return True
            if v in ('0', 'false', 'f', 'n', 'no'):
                return False
            # fallback: Python truthiness
            return bool(raw_value)

        # INT
        if self.tipo == 'INT':
            try:
                return int(raw_value)
            except Exception:
                return int(self.valor_padrao) if self.valor_padrao is not None else None

        # JSON
        if self.tipo == 'JSON':
            try:
                return json.loads(raw_value) if isinstance(raw_value, str) else raw_value
            except Exception:
                return json.loads(self.valor_padrao) if isinstance(self.valor_padrao, str) else self.valor_padrao

        # STRING (default)
        try:
            return raw_value
        except Exception:
            return self.valor_padrao

    def __repr__(self):
        return f'<ConfigDefinicao {self.chave}>'

class EmpresaConfig(db.Model):
    __tablename__ = "empresa_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id', ondelete='CASCADE'), nullable=False)
    chave = db.Column(db.String(100), db.ForeignKey('config_definicoes.chave', ondelete='CASCADE'), nullable=False)
    valor = db.Column(db.Text, nullable=True)

    __table_args__ = (db.UniqueConstraint('empresa_id', 'chave', name='uk_empresa_config'),)

    empresa = db.relationship('Empresa', backref=db.backref('configuracoes', cascade='all, delete-orphan'))
    definicao = db.relationship('ConfigDefinicao')

class ObraConfig(db.Model):
    __tablename__ = "obra_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id', ondelete='CASCADE'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id', ondelete='CASCADE'), nullable=False)
    chave = db.Column(db.String(100), db.ForeignKey('config_definicoes.chave', ondelete='CASCADE'), nullable=False)
    valor = db.Column(db.Text, nullable=True)

    __table_args__ = (db.UniqueConstraint('obra_id', 'chave', name='uk_obra_config'),)

    obra = db.relationship('Obra', backref=db.backref('configuracoes', cascade='all, delete-orphan'))
    definicao = db.relationship('ConfigDefinicao')
