from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import create_app, db
from app.models.usuario import Usuario, Papel, Colaborador, UsuarioPapel
from app.models.empresa import Empresa

def seed():
    app = create_app()
    with app.app_context():
        # 1. Garantir que existe uma empresa
        empresa = Empresa.query.first()
        if not empresa:
            empresa = Empresa(nome="Empresa Inicial")
            db.session.add(empresa)
            db.session.flush()
            print(f"Empresa '{empresa.nome}' criada.")
        
        # 2. Definir papéis padrão
        roles_data = [
            ('Admin', 'Acesso Total ao Sistema'),
            ('Gestor', 'Gestão de Obras e Usuários'),
            ('Operador', 'Lançamento de RDOs'),
            ('Leitor', 'Apenas Visualização'),
            ('Cliente Obra', 'Acesso Externo para Clientes')
        ]
        
        roles_map = {}
        for nome, desc in roles_data:
            role = Papel.query.filter_by(nome=nome, empresa_id=empresa.id).first()
            if not role:
                role = Papel(nome=nome, empresa_id=empresa.id, descricao=desc)
                db.session.add(role)
                db.session.flush()
                print(f"Papel '{nome}' criado.")
            roles_map[nome] = role

        # 3. Garantir que existe um administrador
        admin_role = roles_map.get('Admin')
        admin_user = Usuario.query.join(Usuario.papeis).filter(Papel.nome == 'Admin').first()
        
        if not admin_user:
            # Criar colaborador para o admin
            colab = Colaborador(nome="Administrador Sistema", empresa_id=empresa.id)
            db.session.add(colab)
            db.session.flush()
            
            # Criar usuário admin
            admin_user = Usuario(
                email="admin@sistema.com",
                empresa_id=empresa.id,
                colaborador_id=colab.id,
                ativo=True
            )
            admin_user.set_senha("admin123") # Senha padrão inicial
            db.session.add(admin_user)
            db.session.flush()
            
            # Associar ao papel Admin
            assoc = UsuarioPapel(
                empresa_id=empresa.id,
                usuario_id=admin_user.id,
                papel_id=admin_role.id
            )
            db.session.add(assoc)
            print(f"Usuário administrador criado: admin@sistema.com / admin123")
        
        db.session.commit()
        print("Seed concluído com sucesso!")

if __name__ == "__main__":
    seed()
