from datetime import datetime
from app import db

class Obra(db.Model):
    __tablename__ = "obras"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    nome = db.Column(db.String(150), nullable=False)
    data_inicio = db.Column(db.Date, nullable=True)
    data_fim_planejada = db.Column(db.Date, nullable=True)
    data_fim = db.Column(db.Date, nullable=True)
    
    # Responsável
    usuario_responsavel_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, index=True)

    # Tipo de Obra
    tipo_obra_id = db.Column(db.Integer, db.ForeignKey('aux_tipo_obra.id'), nullable=True, index=True)

    # Vínculo com Cliente
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
    cnpj_obra = db.Column(db.String(20), nullable=True)

    # Endereço Normalizado
    logradouro = db.Column(db.String(200), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(100), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True, index=True)
    estado = db.Column(db.String(2), nullable=True)
    cep = db.Column(db.String(10), nullable=True)

    hora_entrada_padrao = db.Column(db.Time, nullable=True)
    intervalo_entrada_padrao = db.Column(db.Time, nullable=True)
    intervalo_saida_padrao = db.Column(db.Time, nullable=True)
    hora_saida_padrao = db.Column(db.Time, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    empresa = db.relationship('Empresa', backref='obras')
    usuario_responsavel = db.relationship('Usuario', foreign_keys=[usuario_responsavel_id], backref='obras_sob_responsabilidade')
    tipo_obra = db.relationship('AuxTipoObra', backref='obras')
    cliente = db.relationship("Cliente", back_populates="obras")

    # Sinônimos e Propriedades Legado
    status = db.synonym("ativo")
    inicio = db.synonym("data_inicio")
    termino = db.synonym("data_fim")
    horario_entrada = db.synonym("hora_entrada_padrao")
    horario_saida = db.synonym("hora_saida_padrao")
    responsavel = db.synonym("usuario_responsavel")

    @property
    def cnpj(self):
        """Retorna o CNPJ da obra (ou do cliente se não houver um específico para a obra)"""
        return self.cnpj_obra or (self.cliente.cnpj if self.cliente else None)

    @property
    def contratante(self):
        """Alias para o cliente vinculado à obra"""
        return self.cliente.razao_social if self.cliente else None

    @property
    def endereco(self):
        """Gera o endereço completo a partir dos campos normalizados"""
        partes = [self.logradouro]
        if self.numero: partes.append(f"nº {self.numero}")
        if self.complemento: partes.append(self.complemento)
        if self.bairro: partes.append(self.bairro)
        return ", ".join([p for p in partes if p])

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
