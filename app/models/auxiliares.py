from datetime import datetime
from app import db

class AuxClima(db.Model):
    __tablename__ = "aux_clima"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    descricao = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship('Empresa', backref='aux_climas')
    nome = db.synonym("descricao")

    @property
    def tipo_lista(self):
        return "Climas"

    @tipo_lista.setter
    def tipo_lista(self, value):
        pass

    def __repr__(self):
        return f"<AuxClima {self.descricao}>"


class AuxFuncoes(db.Model):
    __tablename__ = "aux_funcoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    descricao = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.Enum('DIRETO', 'INDIRETO'), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship('Empresa', backref='aux_funcoes')
    nome = db.synonym("descricao")

    @property
    def tipo_lista(self):
        return "Mao de Obra"

    @tipo_lista.setter
    def tipo_lista(self, value):
        pass

    def __repr__(self):
        return f"<AuxFuncoes {self.descricao}>"


class AuxEquipamentos(db.Model):
    __tablename__ = "aux_equipamentos"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    descricao = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(100), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship('Empresa', backref='aux_equipamentos')
    nome = db.synonym("descricao")

    @property
    def tipo_lista(self):
        return "Equipamentos"

    @tipo_lista.setter
    def tipo_lista(self, value):
        pass

    def __repr__(self):
        return f"<AuxEquipamentos {self.descricao}>"


class AuxTagOcorrencia(db.Model):
    __tablename__ = "aux_tag_ocorrencia"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    descricao = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(100), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship('Empresa', backref='aux_tags_ocorrencia')
    nome = db.synonym("descricao")

    @property
    def tipo_lista(self):
        return "Tags Ocorrencias"

    @tipo_lista.setter
    def tipo_lista(self, value):
        pass

    def __repr__(self):
        return f"<AuxTagOcorrencia {self.descricao}>"


class AuxTipoObra(db.Model):
    __tablename__ = "aux_tipo_obra"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True, index=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship('Empresa', backref='aux_tipos_obra')

    @property
    def tipo_lista(self):
        return "Tipos de Obra"

    @tipo_lista.setter
    def tipo_lista(self, value):
        pass

    def __repr__(self):
        return f"<AuxTipoObra {self.nome}>"
