"""
Testes para WorkflowService - Branch 7
"""

import pytest
from datetime import datetime, timezone
from app import db
from app.models.workflow import WorkflowDefinicao, WorkflowEtapa
from app.models.rdo import RDO, RDOAprovacao, RDOVersao
from app.models.usuario import Usuario, Papel
from app.models.obra import Obra, FrenteTrabalho
from app.models.empresa import Empresa
from app.services.workflow_service import WorkflowService, WorkflowResolucaoError


class TestWorkflowResolucao:
    """Testes de resolução de workflow."""

    def test_resolver_workflow_obra_prioridade(self, app, db_session, empresa, obra, usuario):
        """Workflow por obra tem prioridade sobre workflow por empresa."""
        with app.app_context():
            # Workflow genérico da empresa
            workflow_empresa = WorkflowDefinicao(
                empresa_id=empresa.id,
                obra_id=None,
                nome="Workflow Empresa",
                aprovacao_paralela=False,
                ativo=True,
            )
            db.session.add(workflow_empresa)

            # Workflow específico da obra
            workflow_obra = WorkflowDefinicao(
                empresa_id=empresa.id,
                obra_id=obra.id,
                nome="Workflow Obra",
                aprovacao_paralela=False,
                ativo=True,
            )
            db.session.add(workflow_obra)
            db.session.commit()

            # Resolve: deve retornar o da obra
            resultado = WorkflowService.resolver_workflow(empresa.id, obra.id)
            assert resultado is not None
            assert resultado.id == workflow_obra.id

    def test_resolver_workflow_empresa_fallback(self, app, db_session, empresa, obra):
        """Sem workflow por obra, retorna workflow da empresa."""
        with app.app_context():
            workflow_empresa = WorkflowDefinicao(
                empresa_id=empresa.id,
                obra_id=None,
                nome="Workflow Empresa",
                ativo=True,
            )
            db.session.add(workflow_empresa)
            db.session.commit()

            resultado = WorkflowService.resolver_workflow(empresa.id, obra.id)
            assert resultado is not None
            assert resultado.id == workflow_empresa.id

    def test_resolver_workflow_nenhum(self, app, empresa, obra):
        """Sem workflow, retorna None."""
        with app.app_context():
            resultado = WorkflowService.resolver_workflow(empresa.id, obra.id)
            assert resultado is None


class TestGeracaoAprovacoes:
    """Testes de geração de aprovações."""

    def test_gerar_aprovacoes_sequenciais(self, app, db_session, empresa, obra, frente_trabalho, usuario, usuario2, usuario3):
        """Gera aprovações em sequência."""
        with app.app_context():
            # Workflow sequencial
            workflow = WorkflowDefinicao(
                empresa_id=empresa.id,
                obra_id=obra.id,
                nome="Sequencial",
                aprovacao_paralela=False,
                ativo=True,
            )
            db.session.add(workflow)
            db.session.flush()

            # 3 etapas sequenciais
            for i, user in enumerate([usuario, usuario2, usuario3], 1):
                etapa = WorkflowEtapa(
                    empresa_id=empresa.id,
                    workflow_id=workflow.id,
                    nivel=i,
                    nome=f"Etapa {i}",
                    usuario_aprovador_id=user.id,
                    obrigatorio=True,
                    sla_horas=24,
                )
                db.session.add(etapa)
            db.session.flush()

            # RDO
            rdo = RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente_trabalho.id,
                status='PENDENTE',
            )
            db.session.add(rdo)
            db.session.flush()

            # Gera aprovações
            aprovacoes = WorkflowService.gerar_aprovacoes_por_etapas(rdo.id, workflow.id)
            
            assert len(aprovacoes) == 3
            assert aprovacoes[0].nivel == 1
            assert aprovacoes[0].aprovador_id == usuario.id
            assert aprovacoes[1].nivel == 2
            assert aprovacoes[1].aprovador_id == usuario2.id
            assert aprovacoes[2].nivel == 3
            assert aprovacoes[2].aprovador_id == usuario3.id

    def test_gerar_aprovacoes_paralelas(self, app, db_session, empresa, obra, frente_trabalho, usuario, usuario2, usuario3):
        """Gera aprovações em paralelo (todas no nível 1)."""
        with app.app_context():
            # Workflow paralelo
            workflow = WorkflowDefinicao(
                empresa_id=empresa.id,
                obra_id=obra.id,
                nome="Paralelo",
                aprovacao_paralela=True,
                ativo=True,
            )
            db.session.add(workflow)
            db.session.flush()

            # 3 etapas (serão todas nível 1)
            for i, user in enumerate([usuario, usuario2, usuario3], 1):
                etapa = WorkflowEtapa(
                    empresa_id=empresa.id,
                    workflow_id=workflow.id,
                    nivel=i,  # Será ignorado em paralelo
                    nome=f"Etapa {i}",
                    usuario_aprovador_id=user.id,
                )
                db.session.add(etapa)
            db.session.flush()

            # RDO
            rdo = RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente_trabalho.id,
                status='PENDENTE',
            )
            db.session.add(rdo)
            db.session.flush()

            # Gera aprovações
            aprovacoes = WorkflowService.gerar_aprovacoes_por_etapas(rdo.id, workflow.id)
            
            assert len(aprovacoes) == 3
            # Todas em nível 1 (paralelo)
            assert all(a.nivel == 1 for a in aprovacoes)


class TestAprovacao:
    """Testes de aprovação de etapas."""

    def test_aprovar_etapa(self, app, db_session, empresa, obra, frente_trabalho, usuario):
        """Aprova uma etapa."""
        with app.app_context():
            # Setup
            rdo = RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente_trabalho.id,
                status='PENDENTE',
            )
            db.session.add(rdo)
            db.session.flush()

            aprov = RDOAprovacao(
                empresa_id=empresa.id,
                rdo_id=rdo.id,
                aprovador_id=usuario.id,
                nivel=1,
                status='PENDENTE',
            )
            db.session.add(aprov)
            db.session.commit()

            # Aprova
            sucesso, msg = WorkflowService.aprovar_etapa(
                aprovacao_id=aprov.id,
                comentario="OK",
                ip="127.0.0.1",
            )

            assert sucesso
            db.session.refresh(aprov)
            assert aprov.status == 'APROVADO'
            assert aprov.comentario == "OK"

    def test_aprovar_ultima_etapa_bloqueia_rdo(self, app, db_session, empresa, obra, frente_trabalho, usuario, usuario2):
        """Aprovar última etapa bloqueia RDO e cria versão."""
        with app.app_context():
            # Setup com 2 aprovações
            rdo = RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente_trabalho.id,
                status='PENDENTE',
                versao=1,
            )
            db.session.add(rdo)
            db.session.flush()

            aprov1 = RDOAprovacao(
                empresa_id=empresa.id,
                rdo_id=rdo.id,
                aprovador_id=usuario.id,
                nivel=1,
                status='APROVADO',
                data_aprovacao=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.session.add(aprov1)

            aprov2 = RDOAprovacao(
                empresa_id=empresa.id,
                rdo_id=rdo.id,
                aprovador_id=usuario2.id,
                nivel=2,
                status='PENDENTE',
            )
            db.session.add(aprov2)
            db.session.commit()

            # Aprova segunda etapa (última)
            sucesso, msg = WorkflowService.aprovar_etapa(
                aprovacao_id=aprov2.id,
                comentario="Finalizado",
                ip="127.0.0.1",
            )

            assert sucesso
            db.session.refresh(rdo)
            assert rdo.status == 'APROVADO'
            assert rdo.bloqueado_em is not None
            
            # Verifica versão criada
            versao = RDOVersao.query.filter_by(rdo_id=rdo.id, numero_versao=1).first()
            assert versao is not None


class TestRejeicao:
    """Testes de rejeição de etapas."""

    def test_rejeitar_etapa(self, app, db_session, empresa, obra, frente_trabalho, usuario, usuario2):
        """Rejeita uma etapa."""
        with app.app_context():
            rdo = RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente_trabalho.id,
                status='PENDENTE',
            )
            db.session.add(rdo)
            db.session.flush()

            aprov = RDOAprovacao(
                empresa_id=empresa.id,
                rdo_id=rdo.id,
                aprovador_id=usuario.id,
                nivel=1,
                status='PENDENTE',
            )
            db.session.add(aprov)
            db.session.commit()

            # Rejeita
            sucesso, msg = WorkflowService.rejeitar_etapa(
                aprovacao_id=aprov.id,
                motivo="Erro de preenchimento",
                ip="127.0.0.1",
                reabrir=True,
            )

            assert sucesso
            db.session.refresh(aprov)
            assert aprov.status == 'REJEITADO'
            db.session.refresh(rdo)
            assert rdo.status == 'RASCUNHO'

    def test_rejeicao_cancela_fluxo(self, app, db_session, empresa, obra, frente_trabalho, usuario, usuario2):
        """Rejeição cancela fluxo se configurado."""
        with app.app_context():
            # Workflow que cancela ao rejeitar
            workflow = WorkflowDefinicao(
                empresa_id=empresa.id,
                obra_id=obra.id,
                nome="Test",
                rejeicao_cancela_fluxo=True,
                ativo=True,
            )
            db.session.add(workflow)
            db.session.flush()

            rdo = RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente_trabalho.id,
                status='PENDENTE',
            )
            db.session.add(rdo)
            db.session.flush()

            # 2 aprovações
            aprov1 = RDOAprovacao(
                empresa_id=empresa.id,
                rdo_id=rdo.id,
                aprovador_id=usuario.id,
                nivel=1,
                status='PENDENTE',
            )
            db.session.add(aprov1)

            aprov2 = RDOAprovacao(
                empresa_id=empresa.id,
                rdo_id=rdo.id,
                aprovador_id=usuario2.id,
                nivel=2,
                status='PENDENTE',
            )
            db.session.add(aprov2)
            db.session.commit()

            # Rejeita primeira
            WorkflowService.rejeitar_etapa(
                aprovacao_id=aprov1.id,
                motivo="Erro",
                ip="127.0.0.1",
                reabrir=False,
            )

            # Segunda deve estar cancelada
            db.session.refresh(aprov2)
            assert aprov2.status == 'CANCELADO'


class TestBloqueio:
    """Testes de bloqueio pós-aprovação."""

    def test_pode_editar_rdo_rascunho(self, app, db_session, empresa, obra, frente_trabalho):
        """RDO em rascunho pode ser editado."""
        with app.app_context():
            rdo = RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente_trabalho.id,
                status='RASCUNHO',
            )
            db.session.add(rdo)
            db.session.commit()

            pode, _ = WorkflowService.pode_editar_rdo(rdo.id)
            assert pode

    def test_pode_editar_rdo_aprovado(self, app, db_session, empresa, obra, frente_trabalho):
        """RDO aprovado não pode ser editado."""
        with app.app_context():
            rdo = RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente_trabalho.id,
                status='APROVADO',
            )
            db.session.add(rdo)
            db.session.commit()

            pode, motivo = WorkflowService.pode_editar_rdo(rdo.id)
            assert not pode
            assert "aprovado" in motivo.lower()


class TestProgresso:
    """Testes de consulta de progresso."""

    def test_obter_progresso_aprovacao(self, app, db_session, empresa, obra, frente_trabalho, usuario, usuario2):
        """Retorna progresso correto de aprovação."""
        with app.app_context():
            rdo = RDO(
                empresa_id=empresa.id,
                obra_id=obra.id,
                frente_trabalho_id=frente_trabalho.id,
            )
            db.session.add(rdo)
            db.session.flush()

            # 1 aprovada, 1 rejeitada, 1 pendente
            RDOAprovacao.query.filter_by(rdo_id=rdo.id).delete()
            
            RDOAprovacao(
                empresa_id=empresa.id, rdo_id=rdo.id, aprovador_id=usuario.id,
                status='APROVADO', nivel=1, data_aprovacao=datetime.now(timezone.utc).replace(tzinfo=None)
            ).save()
            
            RDOAprovacao(
                empresa_id=empresa.id, rdo_id=rdo.id, aprovador_id=usuario2.id,
                status='REJEITADO', nivel=2, data_aprovacao=datetime.now(timezone.utc).replace(tzinfo=None)
            ).save()
            
            RDOAprovacao(
                empresa_id=empresa.id, rdo_id=rdo.id, aprovador_id=usuario.id,
                status='PENDENTE', nivel=3
            ).save()

            db.session.commit()

            progresso = WorkflowService.obter_progresso_aprovacao(rdo.id)
            
            assert progresso['total'] == 3
            assert progresso['aprovadas'] == 1
            assert progresso['rejeitadas'] == 1
            assert progresso['pendentes'] == 1
