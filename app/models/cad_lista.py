from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive

class CadLista(db.Model):
    __tablename__ = "cad_listas"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True, index=True)
    titulo = db.Column(db.String(150), nullable=False)
    nome_interno = db.Column(db.String(150), nullable=False, unique=True)
    slug = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    
    # Enums expandidos conforme recomendação estratégica
    modulo = db.Column(db.Enum(
        'RDO', 'Estoque', 'Suprimentos', 'Administrativo', 'RH', 
        'Configuração', 'Integração', 'Financeiro', 'Engenharia', 'Sistema'
    ), nullable=False, index=True)
    
    tipo_lista = db.Column(db.Enum(
        'Auxiliar', 'Cadastro', 'Transacional', 'Configuração', 
        'Auditoria', 'Log', 'Sistema'
    ), nullable=False, index=True)
    
    origem_dados = db.Column(db.Enum(
        'SharePoint', 'SQL Server', 'MySQL', 'Dataverse', 'API Externa'
    ), nullable=False)

    versao_estrutura = db.Column(db.String(20), default='v1.0')
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, default=True, index=True)
    permite_edicao_usuario = db.Column(db.Boolean, default=False)
    sincronizar_integracoes = db.Column(db.Boolean, default=False)

    # Auditoria automática (FK para usuarios.id)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    modificado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    # Relacionamentos
    empresa = db.relationship('Empresa', backref='listas_cadastradas')
    
    # Nota: Usando string para evitar importação circular se necessário
    criador = db.relationship('Usuario', foreign_keys=[criado_por], backref='listas_criadas')
    modificador = db.relationship('Usuario', foreign_keys=[modificado_por], backref='listas_modificadas')

    def __repr__(self):
        return f"<CadLista {self.nome_interno}>"
