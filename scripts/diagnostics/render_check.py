from datetime import date
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from app import create_app, db
from app.models.auxiliares import AuxClima, AuxEquipamentos, AuxFuncoes, AuxTagOcorrencia
from app.models.empresa import Empresa
from app.models.obra import FrenteTrabalho, Obra, ObraUsuario
from app.models.rdo import RDO
from app.models.usuario import Colaborador, Papel, Usuario, UsuarioPapel
from app.routes.admin import seed_system_roles_and_permissions


PATHS = [
    "/auth/inicio",
    "/auth/lista-rdo",
    "/auth/criar-rdo",
    "/auth/lista-obras",
    "/auth/criar-obra",
    "/auth/lista-usuarios",
    "/auth/criar-usuario",
    "/auth/lista-climas",
    "/auth/criar-clima",
    "/auth/lista-equipamentos",
    "/auth/criar-equipamento",
    "/auth/lista-mao-obra",
    "/auth/criar-mao-obra",
    "/auth/lista-tags-ocorrencias",
    "/auth/criar-tags-ocorrencias",
    "/auth/empresa",
    "/auth/meu-perfil",
    "/auth/validar-documento",
    "/auth/termos",
    "/auth/privacidade",
    "/auth/suporte",
]


def ensure_sample_data():
    seed_system_roles_and_permissions()

    empresa = Empresa.query.first()
    if not empresa:
        empresa = Empresa(nome="Empresa Demo", ativo=True)
        db.session.add(empresa)
        db.session.flush()

    admin_role = Papel.query.filter_by(nome="ADMIN", empresa_id=None).first()

    user = Usuario.query.filter_by(email="admin@sistema.local", empresa_id=empresa.id).first()
    if not user:
        colaborador = Colaborador(nome="Admin Demo", empresa_id=empresa.id, tipo="PROPRIO", ativo=True)
        db.session.add(colaborador)
        db.session.flush()
        user = Usuario(email="admin@sistema.local", empresa_id=empresa.id, colaborador_id=colaborador.id, ativo=True)
        user.set_senha("admin123")
        db.session.add(user)
        db.session.flush()
        db.session.add(UsuarioPapel(empresa_id=empresa.id, usuario_id=user.id, papel_id=admin_role.id, ativo=True))

    if not AuxClima.query.first():
        db.session.add(AuxClima(empresa_id=empresa.id, descricao="Ensolarado", ativo=True))
    if not AuxFuncoes.query.first():
        db.session.add(AuxFuncoes(empresa_id=empresa.id, descricao="Encarregado", tipo="DIRETO", ativo=True))
    if not AuxEquipamentos.query.first():
        db.session.add(AuxEquipamentos(empresa_id=empresa.id, descricao="Retroescavadeira", ativo=True))
    if not AuxTagOcorrencia.query.first():
        db.session.add(AuxTagOcorrencia(empresa_id=empresa.id, descricao="Seguranca", ativo=True))

    obra = Obra.query.filter_by(empresa_id=empresa.id).first()
    if not obra:
        obra = Obra(empresa_id=empresa.id, nome="Obra Demo", ativo=True, data_inicio=date.today(), criado_por=user.id)
        db.session.add(obra)
        db.session.flush()

    frente = FrenteTrabalho.query.filter_by(obra_id=obra.id).first()
    if not frente:
        frente = FrenteTrabalho(empresa_id=empresa.id, obra_id=obra.id, nome="Frente Principal", ativo=True)
        db.session.add(frente)
        db.session.flush()

    if not ObraUsuario.query.filter_by(obra_id=obra.id, usuario_id=user.id).first():
        db.session.add(ObraUsuario(empresa_id=empresa.id, obra_id=obra.id, usuario_id=user.id, ativo=True))

    if not RDO.query.filter_by(empresa_id=empresa.id).first():
        db.session.add(
            RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente.id,
                numero_sequencial=1,
                data_rdo=date.today(),
                status="PENDENTE",
                ativo=True,
                criado_por=user.id,
            )
        )

    db.session.commit()
    return user, empresa


def main():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        user, empresa = ensure_sample_data()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["empresa_id"] = empresa.id
            sess["user_name"] = user.nome
            sess["user_email"] = user.email
            sess["user_role"] = "ADMIN"

        failures = []
        for path in PATHS:
            response = client.get(path)
            print(f"{response.status_code:>3} {path}")
            if response.status_code >= 500:
                failures.append(path)

        obra = Obra.query.filter_by(empresa_id=empresa.id).first()
        frente = FrenteTrabalho.query.filter_by(obra_id=obra.id).first()
        post_response = client.post(
            "/auth/gerar-rdo",
            data={
                "obra_id": str(obra.id),
                "frente_trabalho_id": str(frente.id),
                "data_rdo": date.today().isoformat(),
                "comentarios_gerais": "Diagnostico automatico",
            },
            follow_redirects=False,
        )
        print(f"{post_response.status_code:>3} /auth/gerar-rdo POST")
        if post_response.status_code >= 500:
            failures.append("/auth/gerar-rdo POST")

        if failures:
            raise SystemExit(f"Template failures: {', '.join(failures)}")


if __name__ == "__main__":
    main()
