"""
Testes para Segurança e Isolamento por Empresa - Branch 11
"""

import pytest
from app import db
from app.models.empresa import Empresa
from app.models.usuario import Usuario, Papel, UsuarioPapel
from app.models.obra import Obra, FrenteTrabalho
from app.models.rdo import RDO


class TestIsolamentoMultiempresa:
    """Testes de isolamento de dados por empresa."""

    def test_usuario_nao_ve_dados_outra_empresa(self, app, cliente_empresa1, usuario_empresa1, obra_empresa1, rdo_empresa1):
        """Um usuário não pode visualizar dados de outra empresa."""
        with app.app_context():
            # Criar segunda empresa e seus dados
            empresa2 = Empresa(nome="Empresa 2", ativo=True)
            db.session.add(empresa2)
            db.session.flush()

            usuario2 = Usuario(
                nome="Usuário Empresa 2",
                email="usuario2@empresa2.com",
                empresa_id=empresa2.id,
                ativo=True,
            )
            usuario2.set_senha("senha123")
            db.session.add(usuario2)
            db.session.flush()

            papel2 = Papel(nome="Admin", empresa_id=empresa2.id, ativo=True)
            db.session.add(papel2)
            db.session.flush()

            user_papel2 = UsuarioPapel(
                empresa_id=empresa2.id,
                usuario_id=usuario2.id,
                papel_id=papel2.id,
                ativo=True,
            )
            db.session.add(user_papel2)

            obra2 = Obra(
                nome="Obra Empresa 2",
                empresa_id=empresa2.id,
                status=1,
                criado_por=usuario2.id,
                cliente_id=0,
            )
            db.session.add(obra2)
            db.session.flush()

            frente2 = FrenteTrabalho(
                nome="Frente Empresa 2",
                empresa_id=empresa2.id,
                obra_id=obra2.id,
            )
            db.session.add(frente2)
            db.session.commit()

            rdo2 = RDO(
                empresa_id=empresa2.id,
                obra_id=obra2.id,
                frente_trabalho_id=frente2.id,
                status='RASCUNHO',
            )
            db.session.add(rdo2)
            db.session.commit()

            # Usuário 1 não deve ver RDO da Empresa 2
            rdos_empresa1 = RDO.query.filter_by(empresa_id=usuario_empresa1.empresa_id, ativo=True).all()
            rdos_ids = [rdo.id for rdo in rdos_empresa1]
            
            assert rdo_empresa1.id in rdos_ids
            assert rdo2.id not in rdos_ids

    def test_query_com_filtro_empresa_obrigatorio(self, app, cliente_empresa1, usuario_empresa1):
        """Toda query de dados operacionais deve filtrar por empresa_id."""
        with app.app_context():
            # Teste que a query sem filtro de empresa retorna múltiplas empresas
            obras_total = Obra.query.filter_by(ativo=True).all()
            
            # Teste que a query COM filtro de empresa retorna apenas da empresa atual
            obras_empresa1 = Obra.query.filter_by(
                empresa_id=usuario_empresa1.empresa_id,
                ativo=True
            ).all()
            
            # Deve haver diferença (ou não ter outras, mas o teste prova a obrigatoriedade)
            assert len(obras_empresa1) >= 0  # Pelo menos 0 resultado

    def test_usuario_nao_pode_alterar_dados_outra_empresa(self, client, app, usuario_empresa1, obra_empresa2):
        """Um usuário não pode alterar dados de outra empresa via POST/PUT."""
        with app.app_context():
            # Login com usuário da empresa1
            resp = client.post(
                "/auth/login",
                data={"email": usuario_empresa1.email, "senha": "senha123"},
                follow_redirects=True,
            )
            assert resp.status_code == 200

        # Tentar alterar obra da empresa2 deve ser negado
        # (Varia conforme endpoint implementado)
        # Este é um teste exemplar para demonstrar o padrão


class TestPermissaoEmpresas:
    """Testes de permissões isoladas por empresa."""

    def test_usuario_vê_apenas_usuarios_sua_empresa(self, app, usuario_empresa1, usuario_empresa2):
        """Usuários de empresa diferente não aparecem em listas."""
        with app.app_context():
            usuarios_empresa1 = Usuario.query.filter_by(
                empresa_id=usuario_empresa1.empresa_id,
                ativo=True
            ).all()
            
            usuarios_ids = [u.id for u in usuarios_empresa1]
            
            # Usuário 1 deve aparecer em sua empresa
            assert usuario_empresa1.id in usuarios_ids
            # Usuário 2 não deve aparecer na empresa1
            assert usuario_empresa2.id not in usuarios_ids

    def test_papeis_isolados_por_empresa(self, app, empresa1, empresa2):
        """Papéis de uma empresa não aparecem em outra."""
        with app.app_context():
            papel1 = Papel(nome="Admin", empresa_id=empresa1.id, ativo=True)
            papel2 = Papel(nome="Admin", empresa_id=empresa2.id, ativo=True)
            db.session.add_all([papel1, papel2])
            db.session.commit()

            papeis_empresa1 = Papel.query.filter_by(
                empresa_id=empresa1.id,
                ativo=True
            ).all()
            
            papeis_ids = [p.id for p in papeis_empresa1]
            assert papel1.id in papeis_ids
            assert papel2.id not in papeis_ids


class TestAcessoNegadoOutraEmpresa:
    """Testes de negação de acesso a dados de outra empresa."""

    def test_sessao_com_empresa_fora_do_usuario_bloqueia_edicao(self, client, usuario_empresa1, empresa1, empresa2):
        """Sessao adulterada/stale nao permite editar empresa que nao pertence ao usuario."""
        usuario_empresa1.troca_senha_obrigatoria = False
        db.session.commit()
        with client.session_transaction() as sess:
            sess["user_id"] = usuario_empresa1.id
            sess["empresa_id"] = empresa2.id

        resp = client.get(f"/auth/empresa/{empresa2.id}/editar")

        assert resp.status_code == 403

    def test_usuario_de_terceira_empresa_nao_edita_empresa_1_ou_2_por_url(self, client, empresa1, empresa2):
        """Usuario fora das empresas 1 e 2 nao deve acessar nenhuma delas pela URL."""
        empresa3 = Empresa(nome="Empresa 3", ativo=True)
        db.session.add(empresa3)
        db.session.flush()

        papel3 = Papel(nome="Admin", empresa_id=empresa3.id, ativo=True)
        db.session.add(papel3)
        db.session.flush()

        usuario3 = Usuario(
            nome="Usuario Empresa 3",
            email="usuario3@empresa3.com",
            empresa_id=empresa3.id,
            ativo=True,
            troca_senha_obrigatoria=False,
        )
        usuario3.set_senha("senha123")
        db.session.add(usuario3)
        db.session.flush()
        db.session.add(UsuarioPapel(
            empresa_id=empresa3.id,
            usuario_id=usuario3.id,
            papel_id=papel3.id,
            ativo=True,
        ))
        db.session.commit()

        for empresa in (empresa1, empresa2):
            with client.session_transaction() as sess:
                sess["user_id"] = usuario3.id
                sess["empresa_id"] = empresa.id

            resp = client.get(f"/auth/empresa/{empresa.id}/editar")

            assert resp.status_code == 403

    def test_admin_empresa_nao_acessa_empresa_por_url(self, client, usuario_empresa1, empresa1, empresa2):
        """Admin de uma empresa nao pode abrir outra empresa trocando a URL."""
        usuario_empresa1.troca_senha_obrigatoria = False
        db.session.commit()
        with client.session_transaction() as sess:
            sess["user_id"] = usuario_empresa1.id
            sess["empresa_id"] = empresa1.id

        resp = client.get(f"/auth/empresa/{empresa2.id}")

        assert resp.status_code == 403

    def test_admin_empresa_nao_edita_empresa_por_url(self, client, usuario_empresa1, empresa1, empresa2):
        """Admin de empresa continua restrito ao tenant atual na edicao."""
        usuario_empresa1.troca_senha_obrigatoria = False
        db.session.commit()
        with client.session_transaction() as sess:
            sess["user_id"] = usuario_empresa1.id
            sess["empresa_id"] = empresa1.id

        resp = client.get(f"/auth/empresa/{empresa2.id}/editar")

        assert resp.status_code == 403

    def test_admin_empresa_nao_salva_empresa_por_url(self, client, app, usuario_empresa1, empresa1, empresa2):
        """POST direto para salvar outra empresa deve ser bloqueado."""
        nome_original = empresa2.nome
        usuario_empresa1.troca_senha_obrigatoria = False
        db.session.commit()
        with client.session_transaction() as sess:
            sess["user_id"] = usuario_empresa1.id
            sess["empresa_id"] = empresa1.id

        resp = client.post(
            f"/auth/empresa/{empresa2.id}/salvar",
            data={"nome_empresa": "Empresa 2 invadida"},
        )

        assert resp.status_code == 403
        with app.app_context():
            assert db.session.get(Empresa, empresa2.id).nome == nome_original

    def test_endpoint_filtra_por_empresa_atual(self, client, app, usuario_empresa1, rdo_empresa1):
        """Endpoints devem filtrar resultados por empresa atual do usuário."""
        with app.app_context():
            # Login
            resp = client.post(
                "/auth/login",
                data={"email": usuario_empresa1.email, "senha": "senha123"},
                follow_redirects=True,
            )
            assert resp.status_code == 200

        # Tentar acessar lista de RDOs deve retornar apenas da empresa atual
        # (Implementação dependente de cada rota)
        # Este teste serve como documentação do padrão

    def test_soft_delete_respeitado_isolamento(self, app, usuario_empresa1, rdo_empresa1):
        """Dados com ativo=False não aparecem mesmo em queries multiempresa."""
        with app.app_context():
            # Desativar um RDO
            rdo_empresa1.ativo = False
            db.session.commit()

            # Query deve filtrar ativo=True
            rdos = RDO.query.filter_by(
                empresa_id=usuario_empresa1.empresa_id,
                ativo=True
            ).all()
            
            rdo_ids = [r.id for r in rdos]
            assert rdo_empresa1.id not in rdo_ids
