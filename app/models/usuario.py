from datetime import datetime
from app import db, login_manager
from sqlalchemy.orm import validates
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import bcrypt

from app.utils.datetime_utils import utcnow_naive

# =========================
# RBAC
# empresa_id = NULL → escopo global (is_system)
# is_system = TRUE → imutável, não pode ser deletado
# =========================

class Permissao(db.Model):
    __tablename__ = "permissoes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True, index=True)
    chave = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    def __repr__(self):
        return f'<Permissao {self.chave}>'


class PapelPermissao(db.Model):
    __tablename__ = "papel_permissao"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True, index=True)
    papel_id = db.Column(db.Integer, db.ForeignKey('papeis.id'), nullable=False, index=True)
    permissao_id = db.Column(db.Integer, db.ForeignKey('permissoes.id'), nullable=False, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)


class Papel(db.Model):
    __tablename__ = "papeis"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=True, index=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    permissoes = db.relationship(
        'Permissao',
        secondary='papel_permissao',
        backref=db.backref('papeis', lazy='dynamic')
    )

    def __repr__(self):
        return f'<Papel {self.nome}>'


class UsuarioPapel(db.Model):
    __tablename__ = "usuario_papel"

    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), primary_key=True, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), primary_key=True, index=True)
    papel_id = db.Column(db.Integer, db.ForeignKey('papeis.id'), primary_key=True, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

# =========================
# COLABORADORES E USUÁRIOS
# =========================

class Colaborador(db.Model):
    __tablename__ = "colaboradores"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=True, index=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True, index=True)
    tipo = db.Column(db.Enum('PROPRIO', 'TERCEIRO', 'CLIENTE'), nullable=False, default='PROPRIO')
    cadastro_pessoa_fisica = db.Column(db.String(100), nullable=True)
    nome = db.Column(db.String(150), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    # Relacionamentos
    empresa = db.relationship('Empresa')
    cliente = db.relationship('Cliente', backref='colaboradores_vinculados')

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    @property
    def is_terceiro(self):  
        return self.tipo == 'TERCEIRO' or self.fornecedor_id is not None

    @validates('tipo')
    def validate_tipo(self, key, value):
        if value == 'PROPRIO':
            if self.fornecedor_id is not None or self.cliente_id is not None:
                raise ValueError("Colaborador PRÓPRIO não deve ter fornecedor ou cliente vinculado.")
        elif value == 'TERCEIRO':
            if self.fornecedor_id is None:
                raise ValueError("Colaborador TERCEIRO deve ter um fornecedor vinculado.")
            if self.cliente_id is not None:
                raise ValueError("Colaborador TERCEIRO não deve ter um cliente vinculado.")
        elif value == 'CLIENTE':
            if self.cliente_id is None:
                raise ValueError("Colaborador CLIENTE deve ter um cliente vinculado.")
            if self.fornecedor_id is not None:
                raise ValueError("Colaborador CLIENTE não deve ter um fornecedor vinculado.")
        return value

    def __repr__(self):
        return f'<Colaborador {self.nome}>'


class Usuario(db.Model, UserMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False, index=True)
    colaborador_id = db.Column(db.Integer, db.ForeignKey('colaboradores.id'), nullable=True, index=True)
    email = db.Column(db.String(150), nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    ultimo_login = db.Column(db.DateTime, nullable=True)
    ultimo_login_ip = db.Column(db.String(45), nullable=True)

    criado_por = db.Column(db.Integer, nullable=True)
    modificado_por = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=utcnow_naive)
    modificado_em = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    colaborador = db.relationship('Colaborador', backref='usuarios')
    empresa = db.relationship('Empresa', backref='usuarios')
    papeis = db.relationship('Papel', secondary='usuario_papel', backref=db.backref('usuarios', lazy='dynamic'))
    status = db.synonym("ativo")
    senha = db.synonym("senha_hash")
    data_cadastro = db.synonym("criado_em")

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        """
        Valida a senha contra senha_hash.

        Suporta múltiplos formatos:
        - Werkzeug: pbkdf2:sha256:...
        - Bcrypt: $2a$, $2b$, $2x$, $2y$ (PHP)

        Observação:
        - Werkzeug lança ValueError se a hash estiver malformada.
        - Para evitar erro 500, tratamos essas exceções e retornamos False.
        """
        if not senha:
            return False
        if not self.senha_hash:
            return False
        if not isinstance(self.senha_hash, str) or not self.senha_hash.strip():
            return False

        hash_str = self.senha_hash.strip()

        # Detectar e validar com bcrypt
        if hash_str.startswith(('$2a$', '$2b$', '$2x$', '$2y$')):
            try:
                hash_str_norm = hash_str.strip()

                # Converter $2y$ (PHP) para $2b$ (mais compatível com bcrypt Python)
                # (Faz somente troca do prefixo, preservando o resto do hash)
                if hash_str_norm.startswith('$2y$'):
                    hash_str_norm = '$2b$' + hash_str_norm[len('$2y$'):]

                # Tenta normalizado primeiro; se falhar, tenta o hash original (após strip)
                if bcrypt.checkpw(senha.encode('utf-8'), hash_str_norm.encode('utf-8')):
                    return True
                return bcrypt.checkpw(senha.encode('utf-8'), hash_str.encode('utf-8'))
            except (ValueError, TypeError, AttributeError):
                return False

        # Validar com werkzeug (padrão)
        try:
            return check_password_hash(hash_str, senha)
        except (ValueError, TypeError):
            return False

    @property
    def nome(self):
        if self.colaborador:
            return self.colaborador.nome
        return self.email

    @nome.setter
    def nome(self, value):
        if self.colaborador:
            self.colaborador.nome = value

    @property
    def cpf(self):
        return self.colaborador.cadastro_pessoa_fisica if self.colaborador else None

    @cpf.setter
    def cpf(self, value):
        if self.colaborador:
            self.colaborador.cadastro_pessoa_fisica = value

    @property
    def primeiro_acesso(self):
        return getattr(self, "_primeiro_acesso", False)

    @primeiro_acesso.setter
    def primeiro_acesso(self, value):
        self._primeiro_acesso = bool(value)

    @property
    def telefone(self):
        return getattr(self, "_telefone", "")

    @telefone.setter
    def telefone(self, value):
        self._telefone = value

    @property
    def departamento(self):
        return getattr(self, "_departamento", "")

    @departamento.setter
    def departamento(self, value):
        self._departamento = value

    @property
    def id_supervisor(self):
        return getattr(self, "_id_supervisor", None)

    @id_supervisor.setter
    def id_supervisor(self, value):
        self._id_supervisor = value

    @property
    def obras_permitidas(self):
        return [rel.obra for rel in getattr(self, "obras_alocadas", []) if rel.ativo and rel.obra]

    @obras_permitidas.setter
    def obras_permitidas(self, obras):
        from app.models.obra import ObraUsuario

        self.obras_alocadas = [
            ObraUsuario(
                empresa_id=self.empresa_id,
                obra_id=obra.id,
                usuario_id=self.id,
                ativo=True,
            )
            for obra in obras
            if obra is not None and obra.id is not None
        ]

    @property
    def papel(self):
        """Retorna o nome do primeiro papel do usuário (compatibilidade legada)."""
        if self.papeis:
            return self.papeis[0].nome
        return None

    def tem_permissao(self, chave: str) -> bool:
        """
        Verifica se o usuário possui uma determinada permissão.
        Busca nos papéis atribuídos ao usuário, incluindo papéis globais (is_system).
        """
        for papel in self.papeis:
            for perm in papel.permissoes:
                if perm.chave == chave and perm.ativo:
                    return True
        return False

    def __repr__(self):
        return f'<Usuario {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))
