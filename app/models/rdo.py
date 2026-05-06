from datetime import datetime
from app import db

class RDO(db.Model):
    __tablename__ = "rdo"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False, index=True)
    frente_trabalho_id = db.Column(db.Integer, db.ForeignKey('frente_trabalho.id'), nullable=False, index=True)
    numero_sequencial = db.Column(db.Integer, nullable=True)
    data_rdo = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.Enum('PENDENTE', 'APROVADO', 'REJEITADO'), index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    clima_manha_id = db.Column(db.Integer, db.ForeignKey('aux_clima.id'), nullable=True)
    clima_tarde_id = db.Column(db.Integer, db.ForeignKey('aux_clima.id'), nullable=True)

    hora_entrada = db.Column(db.Time, nullable=True)
    hora_saida = db.Column(db.Time, nullable=True)
    intervalo_entrada = db.Column(db.Time, nullable=True)
    intervalo_saida = db.Column(db.Time, nullable=True)

    observacoes = db.Column(db.Text, nullable=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    obra = db.relationship('Obra', backref='rdos')
    frente_trabalho = db.relationship('FrenteTrabalho', backref='rdos')
    clima_manha = db.relationship('AuxClima', foreign_keys=[clima_manha_id])
    clima_tarde = db.relationship('AuxClima', foreign_keys=[clima_tarde_id])
    data = db.synonym("data_rdo")
    id_sequencial = db.synonym("numero_sequencial")

    @property
    def id_revisao(self):
        return 0

    @property
    def usuario(self):
        from app.models.usuario import Usuario
        return Usuario.query.get(self.criado_por) if self.criado_por else None

    @property
    def id_criado_por(self):
        return self.criado_por

    @property
    def criado(self):
        return self.criado_em

    @property
    def clima_manha_obj(self):
        return self.clima_manha

    @property
    def clima_tarde_obj(self):
        return self.clima_tarde

class RDOMaoObra(db.Model):
    __tablename__ = "rdo_mao_obra"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False, index=True)
    colaborador_id = db.Column(db.Integer, db.ForeignKey('colaboradores.id'), nullable=False, index=True)
    funcao = db.Column(db.String(100), nullable=True)
    quantidade_horas = db.Column(db.Numeric(10, 2), nullable=True)
    tipo_mao_obra = db.Column(db.Enum('PROPRIA', 'TERCEIRO'), nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rdo = db.relationship('RDO', backref=db.backref('maos_obra', cascade='all, delete-orphan', lazy='dynamic'))
    colaborador = db.relationship('Colaborador')

    @property
    def nome_funcao_resolved(self):
        if self.colaborador:
            return self.colaborador.nome
        return self.funcao or "-"

    @property
    def tipo(self):
        return self.tipo_mao_obra

class RDOEquipamento(db.Model):
    __tablename__ = "rdo_equipamentos"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False, index=True)
    equipamento_id = db.Column(db.Integer, db.ForeignKey('aux_equipamentos.id'), nullable=False, index=True)
    quantidade = db.Column(db.Integer, nullable=True)
    horas_utilizadas = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.Enum('OPERANDO', 'PARADO'), nullable=True)
    motivo_parada = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rdo = db.relationship('RDO', backref=db.backref('equipamentos', cascade='all, delete-orphan', lazy='dynamic'))
    equipamento = db.relationship('AuxEquipamentos')

    @property
    def nome_equipamento_resolved(self):
        return self.equipamento.descricao if self.equipamento else "-"

class RDOOcorrencia(db.Model):
    __tablename__ = "rdo_ocorrencias"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False, index=True)
    tipo_ocorrencia = db.Column(db.Integer, db.ForeignKey('aux_tag_ocorrencia.id'), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    impacto = db.Column(db.Enum('BAIXO', 'MEDIO', 'ALTO'), nullable=True)
    tempo_paralisacao = db.Column(db.Numeric(10, 2), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rdo = db.relationship('RDO', backref=db.backref('ocorrencias', cascade='all, delete-orphan', lazy='dynamic'))
    tag_ocorrencia = db.relationship('AuxTagOcorrencia')
    tag_lista = db.synonym("tag_ocorrencia")

class RDOAtividade(db.Model):
    __tablename__ = "rdo_atividades"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rdo = db.relationship('RDO', backref=db.backref('atividades', cascade='all, delete-orphan', lazy='dynamic'))

class RDOFoto(db.Model):
    __tablename__ = "rdo_fotos"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False, index=True)
    arquivo = db.Column(db.String(255), nullable=True)
    comentario = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rdo = db.relationship('RDO', backref=db.backref('fotos', cascade='all, delete-orphan', lazy='dynamic'))

class RDOAprovacao(db.Model):
    __tablename__ = "rdo_aprovacoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'), nullable=False, index=True)
    aprovador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nivel = db.Column(db.Integer, nullable=True)
    status = db.Column(db.Enum('PENDENTE', 'APROVADO', 'REJEITADO'), index=True)
    data_aprovacao = db.Column(db.DateTime, nullable=True)
    comentario = db.Column(db.Text, nullable=True)
    endereco_ip = db.Column(db.String(45), nullable=True)
    hash = db.Column(db.String(255), nullable=True)
    imagem_assinatura = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rdo = db.relationship('RDO', backref=db.backref('aprovacoes', cascade='all, delete-orphan', lazy='dynamic'))
    aprovador = db.relationship('Usuario')
    usuario = db.synonym("aprovador")
    img_assinatura = db.synonym("imagem_assinatura")

    @property
    def motivo_rejeicao(self):
        return self.comentario
