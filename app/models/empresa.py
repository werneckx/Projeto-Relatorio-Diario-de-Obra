from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive

class Empresa(db.Model):
    __tablename__ = "empresa"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(150), nullable=False)
    logo_empresa = db.Column(db.String(255), nullable=True)
    icone_empresa = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    def __repr__(self):
        return f'<Empresa {self.id}: {self.nome}>'

    def get_config(self, chave):
        """Resolve a configuração da empresa com fallback para o sistema"""
        from app.models.configuracao import EmpresaConfig, ConfigDefinicao
        
        # 1. Tenta Config da Empresa
        cfg = EmpresaConfig.query.filter_by(empresa_id=self.id, chave=chave).first()
        if cfg and cfg.valor is not None:
            return cfg.definicao.cast_value(cfg.valor)
        
        # 2. Fallback para Definição (valor_padrao)
        defn = ConfigDefinicao.query.filter_by(chave=chave).first()
        return defn.cast_value(None) if defn else None
