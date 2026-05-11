import sys
import os
from datetime import datetime

# Adicionar o diretório raiz ao path
sys.path.append(os.getcwd())

from app import create_app, db
from app.models import CadLista, Empresa, Usuario

app = create_app()

with app.app_context():
    print("--- Verificando Modelo CadLista ---")
    try:
        # Verificar campos e tipos
        print(f"Tabela: {CadLista.__tablename__}")
        
        # Simular uma instância
        nova_lista = CadLista(
            titulo="Lista de Teste",
            nome_interno="teste_lista",
            slug="teste",
            modulo="Sistema",
            tipo_lista="Sistema",
            origem_dados="MySQL",
            is_system=True
        )
        print(f"Instância criada com sucesso: {nova_lista}")
        
        # Verificar relacionamentos
        print("Relacionamentos mapeados:")
        print(f" - empresa: {hasattr(CadLista, 'empresa')}")
        print(f" - criador: {hasattr(CadLista, 'criador')}")
        print(f" - modificador: {hasattr(CadLista, 'modificador')}")
        
        print("\n--- Verificação Concluída com Sucesso ---")
    except Exception as e:
        print(f"\n[ERRO] Falha na verificação: {e}")
        sys.exit(1)
