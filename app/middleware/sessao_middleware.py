from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app, request, session, redirect, url_for, has_request_context
from flask_login import logout_user

from app import db
from app.models.sessao import SessaoUsuario



def _utcnow_naive() -> datetime:
    """Retorna datetime UTC sem tzinfo (compatível com modelos atuais)."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def init_sessao_middleware(app):
    """Registra hooks de sessão corporativos no Flask app.

    Regras:
    - valida sessão ativa/não expirada/não revogada (via model)
    - atualiza heartbeat em SessaoUsuario
    - NÃO faz commit fragmentado (apenas altera o objeto; commit ocorre na transação da request)
    """

    @app.before_request
    def sessao_before_request():
        # libera endpoints que não exigem login
        # (mantém previsibilidade: decorators e login_manager continuam válidos)
        if request.endpoint in {"auth.login", "auth.setup", "auth.esqueci_senha", "auth.redefinir_senha", "auth.termos", "auth.privacidade", "auth.suporte", "auth.index"}:
            return

        session_uuid = session.get("session_uuid")
        if not session_uuid:
            return

        # IMPORTANTE: SessaoUsuario.token_hash no banco é String.
        # Normalizamos aqui para evitar mismatches de tipo.
        session_uuid = str(session_uuid)


        now = _utcnow_naive()







        # Valida sessão ativa e não expirada.
        try:
            sessao = (
                SessaoUsuario.query.filter(
                    SessaoUsuario.token_hash == session_uuid,
                    SessaoUsuario.ativa.is_(True),
                    SessaoUsuario.expira_em > now,
                ).first()
            )
        except Exception:
            sessao = None


        if not sessao:
            try:
                logout_user()
            except Exception:
                pass


            # Se a sessão expiou / foi inválida, registra trilha de sessão.
            # OBS: evite reimportar SessaoUsuario aqui (era o que gerava UnboundLocalError).
            try:
                from app.models.sessao import AcessoLog

                if session_uuid:
                    sessao_obj = (
                        SessaoUsuario.query.filter(
                            SessaoUsuario.token_hash == session_uuid
                        ).first()
                    )
                    if sessao_obj and sessao_obj.ativa:
                        sessao_obj.ativa = False
                        sessao_obj.encerrada_em = now
                        sessao_obj.motivo_encerramento = "sessão expirada ou inválida"
                        acesso = AcessoLog(
                            empresa_id=sessao_obj.empresa_id,
                            usuario_id=sessao_obj.usuario_id,
                            email=None,
                            acao='SESSAO_EXPIRADA',
                            ip=request.headers.get('X-Forwarded-For', request.remote_addr),
                            user_agent=request.headers.get('User-Agent'),
                            detalhes={"motivo": "sessão expirada ou inválida"},
                        )
                        db.session.add(acesso)
                    db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass


            session.clear()
            return redirect(url_for("auth.login"))

    @app.after_request
    def sessao_after_request(response):
        # persistência acontece no commit da transação principal da request.
        # Portanto aqui só garantimos que o objeto foi marcado como dirty.
        try:
            session_uuid = session.get("session_uuid")
            if session_uuid:
                now = _utcnow_naive()
                sessao = SessaoUsuario.query.filter(
                    SessaoUsuario.token_hash == session_uuid,
                    SessaoUsuario.ativa.is_(True),
                ).first()
                if sessao and sessao.expira_em > now:
                    if hasattr(sessao, "ultimo_acesso_em"):
                        setattr(sessao, "ultimo_acesso_em", now)
        except Exception:
            # não impacta resposta
            pass
        return response

