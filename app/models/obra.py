from datetime import datetime
from app import db

class Obra(db.Model):
    __tablename__ = "obras"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    pai_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)
    nome = db.Column(db.String(150), nullable=False)
    data_inicio = db.Column(db.Date, nullable=True)
    data_fim_planejada = db.Column(db.Date, nullable=True)
    data_fim = db.Column(db.Date, nullable=True)
    
    hora_entrada_padrao = db.Column(db.Time, nullable=True)
    intervalo_entrada_padrao = db.Column(db.Time, nullable=True)
    intervalo_saida_padrao = db.Column(db.Time, nullable=True)
    hora_saida_padrao = db.Column(db.Time, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship('Empresa', backref='obras')
    sub_obras = db.relationship('Obra', backref=db.backref('obra_pai', remote_side=[id]))
    status = db.synonym("ativo")
    inicio = db.synonym("data_inicio")
    termino = db.synonym("data_fim")
    horario_entrada = db.synonym("hora_entrada_padrao")
    horario_saida = db.synonym("hora_saida_padrao")

    @property
    def cnpj(self):
        return getattr(self, "_cnpj", None)

    @cnpj.setter
    def cnpj(self, value):
        self._cnpj = value

    @property
    def contratante(self):
        return getattr(self, "_contratante", None)

    @contratante.setter
    def contratante(self, value):
        self._contratante = value

    @property
    def contrato(self):
        return getattr(self, "_contrato", None)

    @contrato.setter
    def contrato(self, value):
        self._contrato = value

    @property
    def cep(self):
        return getattr(self, "_cep", None)

    @cep.setter
    def cep(self, value):
        self._cep = value

    @property
    def endereco(self):
        return getattr(self, "_endereco", None)

    @endereco.setter
    def endereco(self, value):
        self._endereco = value

    @property
    def numero(self):
        return getattr(self, "_numero", None)

    @numero.setter
    def numero(self, value):
        self._numero = value

    @property
    def complemento(self):
        return getattr(self, "_complemento", None)

    @complemento.setter
    def complemento(self, value):
        self._complemento = value

    @property
    def bairro(self):
        return getattr(self, "_bairro", None)

    @bairro.setter
    def bairro(self, value):
        self._bairro = value

    @property
    def cidade(self):
        return getattr(self, "_cidade", None)

    @cidade.setter
    def cidade(self, value):
        self._cidade = value

    @property
    def estado(self):
        return getattr(self, "_estado", None)

    @estado.setter
    def estado(self, value):
        self._estado = value

    @property
    def responsavel(self):
        return None

    def __repr__(self):
        return f'<Obra {self.id}: {self.nome}>'

class FrenteTrabalho(db.Model):
    __tablename__ = "frente_trabalho"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False, index=True)
    nome = db.Column(db.String(150), nullable=True)
    centro_custo = db.Column(db.String(100), nullable=True)
    data_inicio = db.Column(db.Date, nullable=True)
    data_fim_planejada = db.Column(db.Date, nullable=True)
    data_fim = db.Column(db.Date, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    obra = db.relationship('Obra', backref='frentes_trabalho')
    nome_frente = db.synonym("nome")
    frente_trabalho_id = db.synonym("id")
    data_planejada = db.synonym("data_fim_planejada")

    @property
    def responsavel(self):
        return None

    @property
    def unidade(self):
        return getattr(self, "_unidade", None)

    @unidade.setter
    def unidade(self, value):
        self._unidade = value

    @property
    def qtd_planejada(self):
        return getattr(self, "_qtd_planejada", None)

    @qtd_planejada.setter
    def qtd_planejada(self, value):
        self._qtd_planejada = value

    def __repr__(self):
        return f'<FrenteTrabalho {self.id}: {self.nome}>'

class FrenteColaborador(db.Model):
    __tablename__ = "frente_colaborador"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    frente_id = db.Column(db.Integer, db.ForeignKey('frente_trabalho.id'), nullable=False, index=True)
    colaborador_id = db.Column(db.Integer, db.ForeignKey('colaboradores.id'), nullable=False, index=True)
    funcao_id = db.Column(db.Integer, db.ForeignKey('aux_funcoes.id'), nullable=True)
    data_inicio = db.Column(db.Date, nullable=True)
    data_fim = db.Column(db.Date, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    frente = db.relationship('FrenteTrabalho', backref='colaboradores_alocados')
    colaborador = db.relationship('Colaborador')
    funcao = db.relationship('AuxFuncoes')

    def __repr__(self):
        return f'<FrenteColaborador Frente:{self.frente_id} Colab:{self.colaborador_id}>'

class ObraUsuario(db.Model):
    __tablename__ = "obra_usuario"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    papel_id = db.Column(db.Integer, db.ForeignKey('papeis.id'), nullable=True, index=True)
    ativo = db.Column(db.Boolean, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = db.relationship('Empresa')
    obra = db.relationship('Obra', backref='usuarios_alocados')
    usuario = db.relationship('Usuario', backref='obras_alocadas')
    papel = db.relationship('Papel')

    def __repr__(self):
        return f'<ObraUsuario Obra:{self.obra_id} Usuario:{self.usuario_id}>'
