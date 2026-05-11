from datetime import datetime
from app import db 

class Empresa(db.Model):
    __tablename__ = "empresa"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(150), nullable=False)
    logo_empresa = db.Column(db.String(255), nullable=True)
    icone_empresa = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
