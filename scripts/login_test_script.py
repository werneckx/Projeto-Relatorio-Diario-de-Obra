#!/usr/bin/env python
"""
Script para testar o login usando Flask test client
"""
from app import create_app

def test_login():
    app = create_app()

    with app.test_client() as client:
        # Testar login
        response = client.post('/auth/login',
                             data={'email': 'gestor@horizonte.com.br', 'senha': 'password123'},
                             follow_redirects=False)

        print(f'Status Code: {response.status_code}')
        print(f'Location: {response.headers.get("Location", "N/A")}')

        if response.status_code == 302:  # Redirect após login bem-sucedido
            print('✓ Login bem-sucedido! Redirecionando...')
            return True
        elif response.status_code == 200:
            print('✗ Login falhou - página de login retornada')
            # Verificar se há mensagens de erro na resposta
            if b'E-mail, senha ou status de usu' in response.data:
                print('  → Mensagem de erro de credenciais encontrada')
            return False
        else:
            print(f'✗ Resposta inesperada: {response.status_code}')
            print(f'  → Resposta: {response.data.decode()[:200]}...')
            return False

if __name__ == "__main__":
    test_login()