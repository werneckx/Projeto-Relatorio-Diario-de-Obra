from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------
# Tabela Associativa (Many-to-Many)
# -----------------------
acesso_obras = db.Table('acesso_obras',
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuarios.id'), primary_key=True),
    db.Column('obra_id', db.Integer, db.ForeignKey('obra.id'), primary_key=True)
)

class Usuario(db.Model, UserMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(11), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=False)
    papel = db.Column(db.String(50), nullable=False, default='Leitor')
    data_cadastro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.Integer)
    id_supervisor = db.Column(db.String(120), nullable=True, default=1)

    # RELACIONAMENTO: Lista de obras/matrizes que este usuário pode acessar
    # Para matrizes: armazena a matriz (id_matriz = None)
    # Para outros papéis: pode armazenar filiais específicas se necessário
    obras_permitidas = db.relationship('Obra', secondary=acesso_obras, backref=db.backref('usuarios_autorizados', lazy='dynamic'))

    def set_senha(self, senha):
        self.senha = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha, senha)
    
    def pode_acessar_obra(self, obra):
        """
        Verifica se o usuário pode acessar uma obra específica.
        Retorna True se:
        - O usuário é Admin
        - A obra (matriz ou filial) está em obras_permitidas
        - A obra é uma filial de uma matriz que está em obras_permitidas
        """
        from app.models.obra import Obra
        
        # Admin tem acesso a tudo
        if self.papel == 'Admin':
            return True
        
        # Verifica se é uma obra específica permitida
        if obra in self.obras_permitidas:
            return True
        
        # Verifica se é filial de uma matriz permitida
        if obra.id_matriz and obra.id_matriz > 0:
            # A obra é uma filial, verifica se sua matriz está em obras_permitidas
            matriz = Obra.query.get(obra.id_matriz)
            if matriz and matriz in self.obras_permitidas:
                return True
        
        return False
    
    def get_obras_acessiveis(self):
        """
        Retorna todas as obras que o usuário pode acessar.
        """
        from app.models.obra import Obra
        
        # Admin tem acesso a todas as obras ativas
        if self.papel == 'Admin':
            return Obra.query.filter(Obra.status == 1).all()
        
        # Coleta todas as obras acessíveis
        obras_acessiveis = set(self.obras_permitidas)
        
        # Adiciona todas as filiais das matrizes permitidas
        for obra in self.obras_permitidas:
            # Se for uma matriz (id_matriz = None ou 0)
            if obra.id_matriz is None or obra.id_matriz == 0:
                filiais = Obra.query.filter(Obra.id_matriz == obra.id, Obra.status == 1).all()
                obras_acessiveis.update(filiais)
        
        return list(obras_acessiveis)

    def __repr__(self):
        return f'<Usuario {self.email}>'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))