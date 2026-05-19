#!/usr/bin/env python
"""
Script para resetar a senha de um usuário específico.
Uso: python reset_user_password.py <email> <nova_senha>
"""
import sys
from app import create_app, db
from app.models.usuario import Usuario

if len(sys.argv) < 3:
    print("Uso: python reset_user_password.py <email> <nova_senha>")
    print("Exemplo: python reset_user_password.py gestor@horizonte.com.br password123")
    sys.exit(1)

email = sys.argv[1]
nova_senha = sys.argv[2]

app = create_app()
with app.app_context():
    user = Usuario.query.filter_by(email=email).first()
    
    if not user:
        print(f"Erro: Usuario com email '{email}' nao encontrado.")
        sys.exit(1)
    
    # Reseta a senha
    user.set_senha(nova_senha)
    db.session.commit()
    
    print(f"Senha resetada com sucesso!")
    print(f"Email: {email}")
    print(f"Nova senha: {nova_senha}")
    print(f"Hash gerado: {user.senha_hash}")
