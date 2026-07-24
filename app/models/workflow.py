from app import db
from app.utils.datetime_utils import utcnow_naive


class WorkflowDefinicao(db.Model):
    __tablename__ = "workflow_definicoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)
    codigo = db.Column(db.String(50), nullable=True)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    tipo_fluxo = db.Column(
        db.Enum('SIMPLES', 'SEQUENCIAL', 'PARALELO', 'MATRIZ', 'CLIENTE_INTERNA', 'CONFIGURAVEL'),
        nullable=False,
        default='CONFIGURAVEL',
    )
    aprovacao_paralela = db.Column(db.Boolean, nullable=False, default=False)
    rejeicao_cancela_fluxo = db.Column(db.Boolean, nullable=False, default=True)
    cliente_obrigatorio = db.Column(db.Boolean, nullable=False, default=False)
    assinatura_obrigatoria = db.Column(db.Boolean, nullable=False, default=False)
    permite_reprovar = db.Column(db.Boolean, nullable=False, default=True)
    comentario_reprovacao_obrigatorio = db.Column(db.Boolean, nullable=False, default=True)
    sla_horas = db.Column(db.Integer, nullable=True)
    sla_global_horas = db.Column(db.Integer, nullable=True)
    permite_reabertura = db.Column(db.Boolean, nullable=False, default=True)
    permite_cancelamento = db.Column(db.Boolean, nullable=False, default=True)
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
        db.UniqueConstraint('empresa_id', 'obra_id', 'codigo', name='uk_workflow_empresa_obra_codigo'),
    )

    def __repr__(self):
        return f'<WorkflowDefinicao {self.nome}>'


class WorkflowGrupo(db.Model):
    __tablename__ = "workflow_grupos"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflow_definicoes.id'), nullable=False, index=True)
    nome = db.Column(db.String(100), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    regra_aprovacao = db.Column(
        db.Enum('TODOS', 'QUALQUER'),
        nullable=False,
        default='TODOS',
    )
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    modificado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    empresa = db.relationship('Empresa')
    workflow = db.relationship(
        'WorkflowDefinicao',
        backref=db.backref('grupos', cascade='all, delete-orphan', lazy='dynamic'),
    )
    criador = db.relationship('Usuario', foreign_keys=[criado_por])
    modificador = db.relationship('Usuario', foreign_keys=[modificado_por])

    __table_args__ = (
        db.UniqueConstraint('workflow_id', 'ordem', name='uk_workflow_grupo_ordem'),
    )

    def __repr__(self):
        return f'<WorkflowGrupo Workflow:{self.workflow_id} Ordem:{self.ordem}>'


class WorkflowEtapa(db.Model):
    __tablename__ = "workflow_etapas"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflow_definicoes.id'), nullable=False)
    nivel = db.Column(db.Integer, nullable=False)
    ordem = db.Column(db.Integer, nullable=True)
    codigo = db.Column(db.String(50), nullable=True)
    nome = db.Column(db.String(150), nullable=False)
    tipo_aprovador = db.Column(
        db.Enum('USUARIO', 'PAPEL', 'CLIENTE', 'RESPONSAVEL_OBRA'),
        nullable=True,
        default='USUARIO',
    )
    papel_id = db.Column(db.Integer, db.ForeignKey('papeis.id'), nullable=True, index=True)
    papel_codigo = db.Column(db.String(100), nullable=True)
    usuario_aprovador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, index=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey('workflow_grupos.id'), nullable=True, index=True)
    grupo_paralelo = db.Column(db.Integer, nullable=True)
    obrigatorio = db.Column(db.Boolean, nullable=False, default=True)
    obrigatoria = db.Column(db.Boolean, nullable=False, default=True)
    assinatura_obrigatoria = db.Column(db.Boolean, nullable=False, default=False)
    sla_horas = db.Column(db.Integer, nullable=True)
    permite_reprovar = db.Column(db.Boolean, nullable=False, default=True)
    comentario_reprovacao_obrigatorio = db.Column(db.Boolean, nullable=False, default=True)
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
    grupo = db.relationship('WorkflowGrupo')
    criador = db.relationship('Usuario', foreign_keys=[criado_por])
    modificador = db.relationship('Usuario', foreign_keys=[modificado_por])

    __table_args__ = (
        db.UniqueConstraint('workflow_id', 'nivel', name='uk_workflow_etapa_nivel'),
        db.UniqueConstraint('workflow_id', 'codigo', name='uk_workflow_etapa_codigo'),
    )

    def __repr__(self):
        return f'<WorkflowEtapa Workflow:{self.workflow_id} Nivel:{self.nivel}>'


class WorkflowExecucao(db.Model):
    __tablename__ = "workflow_execucoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False, index=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflow_definicoes.id'), nullable=False, index=True)
    status = db.Column(
        db.Enum('PENDENTE', 'EM_ANDAMENTO', 'APROVADO', 'REJEITADO', 'CANCELADO', 'REABERTO'),
        nullable=False,
        default='PENDENTE',
    )
    etapa_atual_nivel = db.Column(db.Integer, nullable=True)
    workflow_snapshot = db.Column(db.JSON, nullable=False)
    origem = db.Column(db.String(50), nullable=True, default='AUTO')
    iniciado_em = db.Column(db.DateTime, default=utcnow_naive)
    finalizado_em = db.Column(db.DateTime, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    modificado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    empresa = db.relationship('Empresa')
    obra = db.relationship('Obra')
    rdo = db.relationship(
        'RDO',
        backref=db.backref('workflow_execucoes', cascade='all, delete-orphan', lazy='dynamic'),
    )
    workflow = db.relationship('WorkflowDefinicao')
    criador = db.relationship('Usuario', foreign_keys=[criado_por])
    modificador = db.relationship('Usuario', foreign_keys=[modificado_por])

    def __repr__(self):
        return f'<WorkflowExecucao RDO:{self.rdo_id} Workflow:{self.workflow_id}>'


class WorkflowExecucaoEtapa(db.Model):
    __tablename__ = "workflow_execucao_etapas"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    execucao_id = db.Column(db.Integer, db.ForeignKey('workflow_execucoes.id'), nullable=False, index=True)
    etapa_definicao_id = db.Column(db.Integer, db.ForeignKey('workflow_etapas.id'), nullable=True, index=True)
    nivel = db.Column(db.Integer, nullable=False)
    ordem = db.Column(db.Integer, nullable=True)
    nome = db.Column(db.String(150), nullable=False)
    tipo_aprovador = db.Column(
        db.Enum('USUARIO', 'PAPEL', 'CLIENTE', 'RESPONSAVEL_OBRA'),
        nullable=True,
    )
    papel_id = db.Column(db.Integer, db.ForeignKey('papeis.id'), nullable=True, index=True)
    usuario_resolvido_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, index=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey('workflow_grupos.id'), nullable=True, index=True)
    grupo_paralelo = db.Column(db.Integer, nullable=True)
    regra_aprovacao = db.Column(
        db.Enum('TODOS', 'QUALQUER'),
        nullable=False,
        default='TODOS',
    )
    obrigatorio = db.Column(db.Boolean, nullable=False, default=True)
    assinatura_obrigatoria = db.Column(db.Boolean, nullable=False, default=False)
    sla_horas = db.Column(db.Integer, nullable=True)
    status = db.Column(
        db.Enum('PENDENTE', 'APROVADO', 'REJEITADO', 'CANCELADO', 'PULADO'),
        nullable=False,
        default='PENDENTE',
    )
    etapa_snapshot = db.Column(db.JSON, nullable=False)
    aprovado_em = db.Column(db.DateTime, nullable=True)
    comentario = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    modificado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    empresa = db.relationship('Empresa')
    execucao = db.relationship(
        'WorkflowExecucao',
        backref=db.backref('etapas_execucao', cascade='all, delete-orphan', lazy='dynamic'),
    )
    etapa_definicao = db.relationship('WorkflowEtapa')
    papel = db.relationship('Papel')
    usuario_resolvido = db.relationship('Usuario', foreign_keys=[usuario_resolvido_id])
    grupo = db.relationship('WorkflowGrupo')
    criador = db.relationship('Usuario', foreign_keys=[criado_por])
    modificador = db.relationship('Usuario', foreign_keys=[modificado_por])

    __table_args__ = (
        db.UniqueConstraint('execucao_id', 'nivel', 'ordem', name='uk_workflow_execucao_etapa_ordem'),
    )

    def __repr__(self):
        return f'<WorkflowExecucaoEtapa Exec:{self.execucao_id} Nivel:{self.nivel}>'
