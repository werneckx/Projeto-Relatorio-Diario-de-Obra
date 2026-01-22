from app import db
from datetime import date

class Obra(db.Model):
    __tablename__ = "obras"

    id = db.Column(db.Integer, primary_key=True)
    id_matriz = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True)
    nome = db.Column(db.String(120), nullable=False)
    contratante = db.Column(db.String(255), nullable=False)
    contrato = db.Column(db.String(50), unique=True, nullable=False)
    id_responsavel = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    cnpj = db.Column(db.String(14), unique=True, nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    numero = db.Column(db.String(10), nullable=False)
    complemento = db.Column(db.String(50))
    bairro = db.Column(db.String(120), nullable=False)
    cidade = db.Column(db.String(120), nullable=False)
    estado = db.Column(db.String(2), nullable=False)
    cep = db.Column(db.String(8), nullable=False)
    inicio = db.Column(db.Date, nullable=False)
    termino = db.Column(db.Date, nullable=False)
    status = db.Column(db.Integer)
    
    # Relacionamento para facilitar a exibição do nome do responsável
    responsavel = db.relationship('Usuario', foreign_keys=[id_responsavel])
    
    def __repr__(self):
        return f'<Obra {self.id}: {self.nome}>'
    
class Frente_Trabalho(db.Model):
    __tablename__ = "obras_frente_trabalho"
    
    id_frente_trabalho = db.Column(db.Integer, primary_key=True)
    # Garanta que a FK aponte para 'obras.id' (nome da tabela e coluna)
    id_obra = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    # AJUSTE: nullable=True para permitir criar a frente sem atribuir um responsável de imediato
    id_responsavel = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    nome_frente = db.Column(db.String(120), nullable=False)
    unidade = db.Column(db.String(50), nullable=False)
    qtd_planejada = db.Column(db.Float, nullable=False)
    data_planejada = db.Column(db.Date, nullable=True)
    
    responsavel = db.relationship('Usuario', backref='frentes')

    # --- NOVA PROPRIEDADE ---
    @property
    def qtd_realizada(self):
        """Calcula o total realizado somando a qtd_produzida dos RDOs desta frente."""
        from app import db
        from app.models.rdo import RDO
        from sqlalchemy import func
        
        # Soma a coluna qtd_produzida da tabela RDO filtrando pela frente atual
        # Opcional: Adicionar .filter(RDO.status != 'Rejeitado') se quiser ignorar rejeitados
        total = db.session.query(func.sum(RDO.qtd_produzida)).filter(
            RDO.id_frente_trabalho == self.id_frente_trabalho
        ).scalar()
        
        return total if total is not None else 0.0
    
    @property
    def qtd_esperada_curva_s(self):
        """
        Calcula quanto deveria estar pronto hoje usando Curva S (Smoothstep).
        Fórmula: 3t² - 2t³ (t = % do tempo decorrido)
        """
        from datetime import date
        
        # Se não tiver data planejada, não há como calcular meta
        if not self.data_planejada or not self.qtd_planejada:
            return 0.0
        
        # Usa data de início da Obra como base (se a frente não tiver data inicio própria)
        if not self.obra or not self.obra.inicio:
            return 0.0
            
        dt_inicio = self.obra.inicio
        dt_fim = self.data_planejada
        dt_hoje = date.today()
        
        # Cálculo do tempo
        total_dias = (dt_fim - dt_inicio).days
        if total_dias <= 0: 
            return self.qtd_planejada # Evita erro se datas forem iguais ou invertidas
            
        dias_passados = (dt_hoje - dt_inicio).days
        
        # Normaliza o tempo (t) entre 0.0 e 1.0
        t = dias_passados / total_dias
        
        # Limites (Clamping)
        if t <= 0: return 0.0             # Obra ainda não começou
        if t >= 1: return self.qtd_planejada # Obra já deveria ter acabado
        
        # --- A MÁGICA DA CURVA S (Smoothstep) ---
        # Substitui a linha reta (linear) por uma curva suave
        fator_curva = (3 * (t ** 2)) - (2 * (t ** 3))
        
        return self.qtd_planejada * fator_curva

    @property
    def status_prazo(self):
        """Define o farol do KPI automaticamente comparando Real x Curva S"""
        realizado = self.qtd_realizada
        esperado = self.qtd_esperada_curva_s
        
        # Evita divisão por zero no início da obra
        if esperado < 0.01:
            return "Não Iniciado"
            
        # SPI (Schedule Performance Index)
        indice = realizado / esperado
        
        # Regra do Farol (com tolerância de 10%)
        if indice < 0.90:
            return "Atrasado"  # Vermelho
        elif indice > 1.10:
            return "Adiantado" # Azul/Verde Escuro
        else:
            return "No Prazo"  # Verde

    def __repr__(self):
        return f'<Frente {self.nome_frente}>'   