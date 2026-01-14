from datetime import datetime
from app import db 

class RDO(db.Model):
    __tablename__ = "rdo"

    id = db.Column(db.Integer, primary_key=True)
    id_sequencial = db.Column(db.Integer)
    id_revisao = db.Column(db.Integer, default=0)
    
    id_obra = db.Column(db.Integer, db.ForeignKey("obra.id"), nullable=False)
    id_frente_trabalho = db.Column(db.Integer, db.ForeignKey("frente_trabalho.id_frente_trabalho"), nullable=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    
    id_climas_manha = db.Column(db.Integer, db.ForeignKey('clima.id'), nullable=True) 
    id_climas_tarde = db.Column(db.Integer, db.ForeignKey('clima.id'), nullable=True)
    
    data = db.Column(db.Date, nullable=False)
    atividades = db.Column(db.Text)
    status = db.Column(db.String(100))

    # Relacionamentos
    obra = db.relationship("Obra")
    
    usuario = db.relationship(
        "Usuario", 
        primaryjoin="RDO.id_usuario == Usuario.id",
        foreign_keys=[id_usuario],
        backref=db.backref('rdos_criados', lazy='dynamic')
    )
    
    clima_manha_obj = db.relationship(
        'Clima', 
        primaryjoin="RDO.id_climas_manha == Clima.id",
        foreign_keys=[id_climas_manha]
    )
    
    clima_tarde_obj = db.relationship(
        'Clima', 
        primaryjoin="RDO.id_climas_tarde == Clima.id",
        foreign_keys=[id_climas_tarde]
    )

    def __repr__(self):
        return f"<RDO {self.id_sequencial} (Obra ID: {self.id_obra})>"
    
    @property
    def total_mao_obra(self):
        # Como o backref é 'dynamic', usamos .all() para transformar em lista antes de somar
        # Ou usamos uma query de soma do banco (mais rápido para muitos dados)
        return sum(mob.quantidade for mob in self.maos_obra.all())
    
    @property
    def numero_sequencial(self):
        return self.id_sequencial
    
    @numero_sequencial.setter
    def numero_sequencial(self, value):
        self.id_sequencial = value
    
    @property
    def revisao(self):
        return self.id_revisao
    
    @revisao.setter
    def revisao(self, value):
        self.id_revisao = value
        
    # Dentro da classe RDO em rdo.py
    @property
    def obra_id(self):
        return self.id_obra

    @obra_id.setter
    def obra_id(self, value):
        self.id_obra = value
    
    @property
    def usuario_id(self):
        return self.id_usuario

    @usuario_id.setter
    def usuario_id(self, value):
        self.id_usuario = value
        
    @property
    def climas_manha(self):
        return self.id_climas_manha

    @climas_manha.setter
    def climas_manha(self, value):
        self.id_climas_manha = value
    
    @property
    def climas_tarde(self):
        return self.id_climas_tarde

    @climas_tarde.setter
    def climas_tarde(self, value):
        self.id_climas_tarde = value


class Equipamentos(db.Model):
    __tablename__ = 'rdo_equipamentos' # Nome padronizado

    id_equipamento_rdo = db.Column(db.Integer, primary_key=True)
    id_rdo = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    # Se persistir o ID do equipamento da lista de opções:
    id_equipamento_lista = db.Column(db.Integer, db.ForeignKey('lista_opcoes.id'), nullable=True)
    nome_equipamento = db.Column(db.String(255)) # Fallback ou nome copiado
    quantidade = db.Column(db.Integer, default=0)
    
    equipamento_lista = db.relationship('Equipamento')

class Atividades(db.Model):
    __tablename__ = 'rdo_atividades'

    id_atividade = db.Column(db.Integer, primary_key=True)
    id_rdo = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    descricao = db.Column(db.Text) # Text é melhor para descrições longas
    status = db.Column(db.String(50)) # Iniciada, Concluída, etc.

class Fotos(db.Model):
    __tablename__ = 'rdo_fotos'

    id_foto = db.Column(db.Integer, primary_key=True)
    id_rdo = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    arquivo = db.Column(db.String(255), nullable=False) # Nome do arquivo físico
    comentario = db.Column(db.String(255), nullable=True)
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)

class TagsOcorrencias(db.Model):
    __tablename__ = 'rdo_tags_ocorrencias'

    id_tag_rdo = db.Column(db.Integer, primary_key=True)
    id_rdo = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    id_tag_lista = db.Column(db.Integer, db.ForeignKey('lista_opcoes.id'), nullable=True)
    descricao = db.Column(db.Text)
    
    tag_lista = db.relationship('TagOcorrencia')

    
class Assinatura(db.Model):
    __tablename__ = 'rdo_assinaturas'

    id_assinatura = db.Column(db.Integer, primary_key=True)
    id_rdo = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    # New Field: Determines the sequence (1, 2, 3...)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    
    # Workflow Status: 'Pendente', 'Aprovado', 'Rejeitado'
    status = db.Column(db.String(50), default='Pendente') 
    
    # Nullable fields (filled only upon action)
    img_assinatura = db.Column(db.Text, nullable=True) 
    ip_endereco = db.Column(db.String(50), nullable=True)
    validacao = db.Column(db.String(255)) # Hash ou token de validação
    criado = db.Column(db.DateTime, default=datetime.utcnow)
    motivo_rejeicao = db.Column(db.String(255), nullable=True)

    usuario = db.relationship("Usuario", backref="assinaturas_workflow")
    rdo = db.relationship('RDO', backref=db.backref('assinaturas', lazy='dynamic'))