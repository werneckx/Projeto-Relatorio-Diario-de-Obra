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

    # RELACIONAMENTO: Lista de obras que este usuário pode acessar
    obras_permitidas = db.relationship('Obra', secondary=acesso_obras, backref=db.backref('usuarios_autorizados', lazy='dynamic'))

    def set_senha(self, senha):
        self.senha = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha, senha)

    def __repr__(self):
        return f'<Usuario {self.email}>'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))