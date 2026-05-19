from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask_login import logout_user

from app import db
from app.models.sessao import SessaoUsuario, AcessoLog
from app.services.auditoria_service import AuditoriaService


class AuthService:
    @staticmethod
    def revogar_sessao(session_uuid: str, *, motivo: Optional[str] = "logout remoto") -> None:
        """Logout remoto corporativo.

        Regras:
        - NÃO faz commit/rollback
        - apenas altera estado do modelo + registra auditoria/logs
        """

        if not session_uuid:
            return

        now = datetime.utcnow()

        # localiza sessão ativa por token_hash
        sessao = (
            SessaoUsuario.query.filter(
                SessaoUsuario.token_hash == session_uuid,
                SessaoUsuario.ativa.is_(True),
            ).first()
        )

        if not sessao:
            return

        sessao.ativa = False
        sessao.encerrada_em = now
        # compatível com schema atual: encerrada_por é FK para Usuario
        sessao.motivo_encerramento = motivo

        # Auditoria operacional
        AuditoriaService.registrar_evento(
            acao="LOGOUT_REMOTO",
            entidade="SESSAO",
            entidade_id=None,
            dados_antes={"ativa": True, "token_hash": session_uuid},
            dados_depois={"ativa": False, "encerrada_em": now},
            ip=None,
            user_agent=None,
            endpoint=None,
            metodo_http=None,
            payload={"session_uuid": session_uuid, "motivo": motivo},
            empresa_id=sessao.empresa_id,
            usuario_id=sessao.usuario_id,
        )

        # AcessoLog (opcional mas desejado para trilha de observabilidade)
        try:
            acesso = AcessoLog(
                empresa_id=sessao.empresa_id,
                usuario_id=sessao.usuario_id,
                email=None,
                acao="LOGOUT_REMOTO",
                ip=None,
                user_agent=None,
                detalhes={"motivo": motivo},
            )
            db.session.add(acesso)
        except Exception:
            # não quebra fluxo
            pass

        # invalida sessão Flask se o token atual é o mesmo
        try:
            logout_user()
        except Exception:
            pass

