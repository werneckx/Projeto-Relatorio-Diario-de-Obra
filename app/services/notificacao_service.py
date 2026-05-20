from datetime import datetime
from flask import url_for
from app import db
from app.models.notificacao import Notificacao, TipoNotificacao
from app.services.auditoria_service import AuditoriaService
from app.utils.datetime_utils import utcnow_naive


class NotificacaoService:
    """Serviço para gerenciamento seguro e otimizado de Notificações."""

    @staticmethod
    def criar_notificacao(
        empresa_id,
        usuario_id,
        tipo,
        titulo,
        mensagem,
        link=None,
        obra_id=None,
        rdo_id=None,
        referencia_tipo=None,
        referencia_id=None,
        url_destino=None,
        criado_por=None
    ):
        # Trata links e destinos equivalentes
        if rdo_id and not link and not url_destino:
            lnk_url = url_for('auth.visualizar_rdo', rdo_id=rdo_id)
        else:
            lnk_url = link or url_destino

        # Normaliza link salvo no banco: garante barra inicial para caminhos relativos
        if lnk_url and isinstance(lnk_url, str) and not (lnk_url.startswith('/') or lnk_url.startswith('http')):
            lnk_url = '/' + lnk_url.lstrip('/')

        notificacao = Notificacao(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem,
            link=lnk_url,
            obra_id=obra_id,
            rdo_id=rdo_id,
            criado_por=criado_por,
            lida=False,
            ativo=True
        )

        db.session.add(notificacao)
        # Flush para obter o ID gerado antes de registrar auditoria
        db.session.flush()

        # Registro na auditoria centralizada
        AuditoriaService.registrar_auditoria_entidade(
            acao="CREATE",
            entidade="NOTIFICACAO",
            entidade_id=notificacao.id,
            depois=notificacao
        )

        return notificacao

    @staticmethod
    def listar_nao_lidas(usuario_id, empresa_id, limit=10):
        """Lista as notificações não lidas e ativas com limitador de performance."""
        if not usuario_id or not empresa_id:
            return []

        return (
            Notificacao.query
            .filter_by(
                usuario_id=usuario_id,
                empresa_id=empresa_id,
                lida=False,
                ativo=True
            )
            .order_by(Notificacao.criado_em.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def marcar_como_lida(notificacao_id, usuario_id):
        """Marca uma notificação como lida com validação estrita de propriedade (ID tampering)."""
        notificacao = (
            Notificacao.query
            .filter(
                Notificacao.id == notificacao_id,
                Notificacao.usuario_id == usuario_id,
                Notificacao.ativo == True
            )
            .first()
        )

        if not notificacao:
            return None

        notificacao.lida = True
        notificacao.lida_em = utcnow_naive()

        db.session.commit()
        return notificacao
