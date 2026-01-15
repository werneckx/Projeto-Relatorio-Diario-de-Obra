from datetime import datetime
from app import db 

class RDO(db.Model):
    __tablename__ = "rdo"

    id = db.Column(db.Integer, primary_key=True)
    id_sequencial = db.Column(db.Integer)
    id_revisao = db.Column(db.Integer, default=0)
    
    # Chaves Estrangeiras
    id_obra = db.Column(db.Integer, db.ForeignKey("obras.id"), nullable=False)
    id_frente_trabalho = db.Column(db.Integer, db.ForeignKey("obras_frente_trabalho.id_frente_trabalho"), nullable=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    
    # Climas
    id_climas_manha = db.Column(db.Integer, db.ForeignKey('lista_opcoes.id'), nullable=True) 
    id_climas_tarde = db.Column(db.Integer, db.ForeignKey('lista_opcoes.id'), nullable=True)

    # Relacionamentos de Clima
    clima_manha_obj = db.relationship('Clima', foreign_keys=[id_climas_manha])
    clima_tarde_obj = db.relationship('Clima', foreign_keys=[id_climas_tarde])

    # Dados Gerais
    data = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(100)) # Pendente, Revisado, Aprovado, Rejeitado
    comentarios_gerais = db.Column(db.Text, nullable=True)

    # Campos de Horário (Novos)
    hora_entrada = db.Column(db.Time, nullable=True)
    hora_saida = db.Column(db.Time, nullable=True)
    intervalo_entrada = db.Column(db.Time, nullable=True)
    intervalo_saida = db.Column(db.Time, nullable=True)
    
    # Relacionamentos Filhos (Cascade para deletar filhos se o RDO for deletado)
    maos_obra = db.relationship('RDOMaoObra', backref='rdo', cascade='all, delete-orphan', lazy='dynamic')
    equipamentos = db.relationship('Equipamentos', backref='rdo', cascade='all, delete-orphan', lazy='dynamic')
    atividades = db.relationship('Atividades', backref='rdo', cascade='all, delete-orphan', lazy='dynamic')
    fotos = db.relationship('Fotos', backref='rdo', cascade='all, delete-orphan', lazy='dynamic')
    ocorrencias = db.relationship('TagsOcorrencias', backref='rdo', cascade='all, delete-orphan', lazy='dynamic')
    
    # [FIX 6] Remover onupdate=utcnow para evitar sobrescrita do Timezone BR
    criado = db.Column(db.DateTime, default=datetime.utcnow)
    modificado = db.Column(db.DateTime, default=datetime.utcnow) # Remove onupdate
    
    obra = db.relationship("Obra")
    usuario = db.relationship("Usuario", foreign_keys=[id_usuario])
    frente_trabalho = db.relationship("Frente_Trabalho", foreign_keys=[id_frente_trabalho])

    @property
    def numero_sequencial(self):
        return self.id_sequencial

class RDOMaoObra(db.Model):
    __tablename__ = 'rdo_mao_obra'

    id_mao_obra = db.Column(db.Integer, primary_key=True)

    id_rdo = db.Column(
        db.Integer,
        db.ForeignKey('rdo.id'),
        nullable=False
    )

    nome_funcao = db.Column(db.String(100))

    quantidade_propria = db.Column(db.Integer, default=0)
    quantidade_terceirizada = db.Column(db.Integer, default=0)

    tempo = db.Column(db.Time, nullable=True)


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
    def aprovar(self, img_assinatura, ip_endereco):
        self.status = 'Aprovado'
        self.img_assinatura = img_assinatura
        self.ip_endereco = ip_endereco