from datetime import datetime
from app import db
from app.utils.datetime_utils import utcnow_naive


class WorkflowDefinicao(db.Model):
    __tablename__ = "workflow_definicoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    aprovacao_paralela = db.Column(db.Boolean, nullable=False, default=False)
    rejeicao_cancela_fluxo = db.Column(db.Boolean, nullable=False, default=True)
    sla_horas = db.Column(db.Integer, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    modificado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    empresa = db.relationship('Empresa', backref='workflows')
    obra = db.relationship('Obra', backref='workflows')
    criador = db.relationship('Usuario', foreign_keys=[criado_por])
    modificador = db.relationship('Usuario', foreign_keys=[modificado_por])

    __table_args__ = (
        db.UniqueConstraint('empresa_id', 'obra_id', 'nome', name='uk_workflow_empresa_obra_nome'),
    )

    def __repr__(self):
        return f'<WorkflowDefinicao {self.nome}>'


class WorkflowEtapa(db.Model):
    __tablename__ = "workflow_etapas"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflow_definicoes.id'), nullable=False)
    nivel = db.Column(db.Integer, nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    papel_id = db.Column(db.Integer, db.ForeignKey('papeis.id'), nullable=True, index=True)
    usuario_aprovador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, index=True)
    obrigatorio = db.Column(db.Boolean, nullable=False, default=True)
    sla_horas = db.Column(db.Integer, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    modificado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    empresa = db.relationship('Empresa')
    workflow = db.relationship(
        'WorkflowDefinicao',
        backref=db.backref('etapas', cascade='all, delete-orphan', lazy='dynamic'),
    )
    papel = db.relationship('Papel')
    usuario_aprovador = db.relationship('Usuario', foreign_keys=[usuario_aprovador_id])
    criador = db.relationship('Usuario', foreign_keys=[criado_por])
    modificador = db.relationship('Usuario', foreign_keys=[modificado_por])

    __table_args__ = (
        db.UniqueConstraint('workflow_id', 'nivel', name='uk_workflow_etapa_nivel'),
    )

    def __repr__(self):
        return f'<WorkflowEtapa Workflow:{self.workflow_id} Nivel:{self.nivel}>'
