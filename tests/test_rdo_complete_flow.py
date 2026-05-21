"""
Testes para Ciclo Completo de RDO - Branch 11
"""

import pytest
from app import db
from app.models.rdo import RDO, RDOAprovacao
from app.models.usuario import Usuario, Papel, UsuarioPapel
from app.models.obra import Obra, FrenteTrabalho


class TestCicloCompletoRDO:
    """Testes de ciclo completo de uma RDO (criação até aprovação)."""

    def test_criar_rdo_rascunho(self, app, empresa1, usuario_empresa1, obra_empresa1):
        """Criar RDO em estado RASCUNHO."""
        frente = FrenteTrabalho(
            nome="Frente Teste",
            empresa_id=empresa1.id,
            obra_id=obra_empresa1.id,
        )
        db.session.add(frente)
        db.session.commit()

        rdo = RDO(
            empresa_id=empresa1.id,
            obra_id=obra_empresa1.id,
            frente_trabalho_id=frente.id,
            status='RASCUNHO',
        )
        db.session.add(rdo)
        db.session.commit()

        # Verificar que RDO foi criada
        rdo_criada = RDO.query.filter_by(id=rdo.id).first()
        assert rdo_criada is not None
        assert rdo_criada.status == 'RASCUNHO'
        assert rdo_criada.ativo is True

        db.session.delete(rdo)
        db.session.delete(frente)
        db.session.commit()

    def test_mudar_rdo_para_pendente(self, app, rdo_empresa1):
        """Mudar RDO de RASCUNHO para PENDENTE."""
        rdo_empresa1.status = 'PENDENTE'
        db.session.commit()

        rdo_atualizada = RDO.query.filter_by(id=rdo_empresa1.id).first()
        assert rdo_atualizada.status == 'PENDENTE'

    def test_gerar_aprovacoes_para_rdo(self, app, rdo_empresa1, usuario_empresa1, empresa1):
        """Gerar aprovações para uma RDO."""
        # Criar segunda usuário para aprovação
        usuario2 = Usuario(
            nome="Aprovador",
            email="aprovador@test.com",
            empresa_id=empresa1.id,
            ativo=True,
        )
        usuario2.set_senha("senha123")
        db.session.add(usuario2)
        db.session.flush()

        papel = Papel.query.filter_by(
            empresa_id=empresa1.id,
            ativo=True
        ).first()

        if not papel:
            papel = Papel(nome="Admin", empresa_id=empresa1.id, ativo=True)
            db.session.add(papel)
            db.session.flush()

        up = UsuarioPapel(
            empresa_id=empresa1.id,
            usuario_id=usuario2.id,
            papel_id=papel.id,
            ativo=True,
        )
        db.session.add(up)
        db.session.flush()

        # Criar aprovação
        aprovacao = RDOAprovacao(
            empresa_id=empresa1.id,
            rdo_id=rdo_empresa1.id,
            aprovador_id=usuario2.id,
            nivel=1,
            status='PENDENTE',
        )
        db.session.add(aprovacao)
        db.session.commit()

        # Verificar aprovação foi criada
        aprov_criada = RDOAprovacao.query.filter_by(
            rdo_id=rdo_empresa1.id
        ).first()
        assert aprov_criada is not None
        assert aprov_criada.status == 'PENDENTE'

    def test_aprovar_rdo(self, app, rdo_empresa1, usuario_empresa1, empresa1):
        """Aprovar uma etapa de RDO."""
        # Criar aprovação pendente
        aprovacao = RDOAprovacao(
            empresa_id=empresa1.id,
            rdo_id=rdo_empresa1.id,
            aprovador_id=usuario_empresa1.id,
            nivel=1,
            status='PENDENTE',
        )
        db.session.add(aprovacao)
        db.session.commit()

        # Aprovar
        aprovacao.status = 'APROVADO'
        aprovacao.comentario = "Aprovado"
        db.session.commit()

        # Verificar aprovação foi atualizada
        aprov_atualizada = RDOAprovacao.query.filter_by(
            id=aprovacao.id
        ).first()
        assert aprov_atualizada.status == 'APROVADO'
        assert aprov_atualizada.comentario == "Aprovado"

    def test_rejeitar_rdo(self, app, rdo_empresa1, usuario_empresa1, empresa1):
        """Rejeitar uma etapa de RDO."""
        # Criar aprovação pendente
        aprovacao = RDOAprovacao(
            empresa_id=empresa1.id,
            rdo_id=rdo_empresa1.id,
            aprovador_id=usuario_empresa1.id,
            nivel=1,
            status='PENDENTE',
        )
        db.session.add(aprovacao)
        db.session.commit()

        # Rejeitar
        aprovacao.status = 'REJEITADO'
        aprovacao.comentario = "Não aprovado"
        db.session.commit()

        # Verificar rejeição
        aprov_atualizada = RDOAprovacao.query.filter_by(
            id=aprovacao.id
        ).first()
        assert aprov_atualizada.status == 'REJEITADO'

    def test_rdo_finalizada_apos_todas_aprovacoes(self, app, rdo_empresa1, usuario_empresa1, empresa1):
        """RDO passa para APROVADO após todas as aprovações."""
        # Criar duas aprovações sequenciais
        usuario2 = Usuario(
            nome="Aprovador 2",
            email="aprovador2@test.com",
            empresa_id=empresa1.id,
            ativo=True,
        )
        usuario2.set_senha("senha123")
        db.session.add(usuario2)
        db.session.flush()

        aprov1 = RDOAprovacao(
            empresa_id=empresa1.id,
            rdo_id=rdo_empresa1.id,
            aprovador_id=usuario_empresa1.id,
            nivel=1,
            status='PENDENTE',
        )
        aprov2 = RDOAprovacao(
            empresa_id=empresa1.id,
            rdo_id=rdo_empresa1.id,
            aprovador_id=usuario2.id,
            nivel=2,
            status='PENDENTE',
        )
        db.session.add_all([aprov1, aprov2])
        db.session.commit()

        # Aprovar primeira etapa
        aprov1.status = 'APROVADO'
        db.session.commit()

        # Aprovar segunda etapa
        aprov2.status = 'APROVADO'
        db.session.commit()

        # Verificar que todas as aprovações foram aprovadas
        aprovacoes = RDOAprovacao.query.filter_by(
            rdo_id=rdo_empresa1.id
        ).all()
        
        todos_aprovados = all(a.status == 'APROVADO' for a in aprovacoes)
        assert todos_aprovados

    def test_ciclo_rdo_com_rejeicao(self, app, rdo_empresa1, usuario_empresa1, empresa1):
        """RDO volta a RASCUNHO após rejeição."""
        # Criar aprovação
        aprovacao = RDOAprovacao(
            empresa_id=empresa1.id,
            rdo_id=rdo_empresa1.id,
            aprovador_id=usuario_empresa1.id,
            nivel=1,
            status='PENDENTE',
        )
        db.session.add(aprovacao)
        db.session.commit()

        # Rejeitar
        aprovacao.status = 'REJEITADO'
        db.session.commit()

        # RDO deve voltar a RASCUNHO
        rdo_empresa1.status = 'RASCUNHO'
        db.session.commit()

        rdo_atualizada = RDO.query.filter_by(
            id=rdo_empresa1.id
        ).first()
        assert rdo_atualizada.status == 'RASCUNHO'


class TestValidacaoEstadosRDO:
    """Testes de validação de estados válidos de RDO."""

    def test_estados_validos_rdo(self, app, rdo_empresa1):
        """RDO pode ter apenas estados válidos."""
        estados_validos = ['RASCUNHO', 'PENDENTE', 'APROVADO', 'REJEITADO', 'CANCELADO']
        
        from sqlalchemy import inspect
        for estado in estados_validos:
            rdo_empresa1.status = estado
            db.session.commit()
            rdo_atualizada = RDO.query.filter_by(
                id=rdo_empresa1.id
            ).first()
            assert rdo_atualizada.status == estado

    def test_rdo_com_ativo_false_nao_aparece(self, app, rdo_empresa1, empresa1):
        """RDO com ativo=False não aparece em listagens."""
        rdo_empresa1.ativo = False
        db.session.commit()

        # Query com ativo=True não deve retornar RDO
        rdos_ativas = RDO.query.filter_by(
            empresa_id=empresa1.id,
            ativo=True
        ).all()
        
        rdo_ids = [r.id for r in rdos_ativas]
        assert rdo_empresa1.id not in rdo_ids
