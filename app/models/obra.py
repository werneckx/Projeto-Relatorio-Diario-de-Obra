from app import db
from datetime import date
from sqlalchemy import func

class Obra(db.Model):
    __tablename__ = "obras"

    id = db.Column(db.Integer, primary_key=True)
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
    id_obra = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    id_responsavel = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    nome_frente = db.Column(db.String(120), nullable=False)
    unidade = db.Column(db.String(50), nullable=False)
    qtd_planejada = db.Column(db.Float, nullable=False)
    data_inicio = db.Column(db.Date, nullable=True)
    data_planejada = db.Column(db.Date, nullable=True)
    
    responsavel = db.relationship('Usuario', backref='frentes')
    obra = db.relationship('Obra', backref='frentes_trabalho')
    
    @property
    def qtd_realizada(self):
        """Calcula o total realizado somando a qtd_produzida dos RDOs aprovados/pendentes desta frente."""
        # Importação local para evitar ciclo, pois RDO importa Frente_Trabalho
        from app.models.rdo import RDO
        
        # Filtra RDOs para NÃO somar os Rejeitados
        # Se o RDO foi rejeitado, o trabalho não conta como realizado oficial
        total = db.session.query(func.sum(RDO.qtd_produzida)).filter(
            RDO.id_frente_trabalho == self.id_frente_trabalho,
            RDO.status != 'Rejeitado'
        ).scalar()
        
        return total if total is not None else 0.0
    
    @property
    def qtd_esperada_curva_s(self):
        """
        Calcula quanto deveria estar pronto hoje usando Curva S (Smoothstep).
        Retorna a QUANTIDADE (na unidade da frente) esperada.
        """
        # Se não tiver meta ou data final, expectativa é 0
        if not self.data_planejada or not self.qtd_planejada:
            return 0.0
        
        # Lógica de Data de Início:
        # 1. Usa data específica da Frente
        # 2. Fallback para data da Obra Pai
        dt_inicio = self.data_inicio
        if not dt_inicio and self.obra:
             dt_inicio = self.obra.inicio

        # Se ainda assim não tiver data, não calcula
        if not dt_inicio:
            return 0.0

        dt_fim = self.data_planejada
        dt_hoje = date.today()
        
        # Cálculo de dias totais do cronograma
        total_dias = (dt_fim - dt_inicio).days
        
        # Se a data fim é igual ou anterior ao inicio, assume 100% se hoje >= fim
        if total_dias <= 0: 
            return self.qtd_planejada if dt_hoje >= dt_fim else 0.0
            
        dias_passados = (dt_hoje - dt_inicio).days
        
        # Normaliza o tempo (t) entre 0.0 e 1.0
        t = dias_passados / total_dias
        
        # Se ainda não começou
        if t <= 0: return 0.0             
        # Se já acabou o prazo
        if t >= 1: return self.qtd_planejada 
        
        # Fórmula Smoothstep (3x² - 2x³) para gerar a Curva S
        # Isso cria uma progressão mais lenta no início, acelera no meio, e desacelera no fim
        fator_curva = (3 * (t ** 2)) - (2 * (t ** 3))
        
        return self.qtd_planejada * fator_curva
    
    @property
    def status_prazo(self):
        """KPI Farol: Compara Realizado vs Esperado (SPI - Schedule Performance Index)"""
        realizado = self.qtd_realizada
        esperado = self.qtd_esperada_curva_s
        
        # Evita divisão por zero ou início prematuro
        if esperado < 0.01:
            # Se já realizou algo mas 'esperado' é zero (ex: começou antes da data), está adiantado
            if realizado > 0:
                return "Adiantado"
            return "Não Iniciado"
            
        # SPI = Índice de Desempenho de Prazo
        indice = realizado / esperado
        
        if indice < 0.90:
            return "Atrasado"  # Vermelho (< 90% do esperado)
        elif indice > 1.10:
            return "Adiantado" # Verde (> 110% do esperado)
        else:
            return "No Prazo"  # Azul (Entre 90% e 110%)