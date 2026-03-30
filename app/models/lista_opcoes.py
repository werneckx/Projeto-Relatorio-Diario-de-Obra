from app import db

class ListaOpcaoBase(db.Model):
    __tablename__ = "lista_opcoes"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    tipo_lista = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(50), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)

    __mapper_args__ = {
        'polymorphic_on': tipo_lista,
    }

class Clima(ListaOpcaoBase):
    __mapper_args__ = {
        'polymorphic_identity': 'Climas',
    }

class Equipamento(ListaOpcaoBase):
    __mapper_args__ = {
        'polymorphic_identity': 'Equipamentos',
    }
    
class TagOcorrencia(ListaOpcaoBase):
    __mapper_args__ = {
        'polymorphic_identity': 'Tags Ocorrencias',
    }
    
class MaoObra(ListaOpcaoBase):
    __mapper_args__ = {
        'polymorphic_identity': 'Mao de Obra',
    }