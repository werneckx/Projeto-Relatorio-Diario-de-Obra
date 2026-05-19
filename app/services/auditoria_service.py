from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import current_app
from flask_login import current_user

from app import db
from app.models.auditoria import AuditoriaLog
from app.utils.serializers import SENSITIVE_FIELDS
from app.utils.serializers import safe_model_to_dict
from app.utils.request_context import capturar_request_context


class AuditoriaService:
    """Serviço centralizado de auditoria (transacional).

    Regras estritas:
    - NÃO commit
    - NÃO rollback
    - NÃO flush explícito
    - NÃO depende de views
    - Apenas db.session.add(...)
    """

    @staticmethod
    def registrar_auditoria_entidade(
        *,
        acao: str,
        entidade: str,
        entidade_id: Optional[int] = None,
        antes: Optional[Any] = None,
        depois: Optional[Any] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Wrapper único para auditoria before/after.

        - Centraliza serialização segura e multi-tenant via AuditoriaService.capturar_contexto()
        - Não executa commit/rollback.
        """
        ctx = AuditoriaService.capturar_contexto()

        AuditoriaService.registrar_operacao(
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            antes=antes,
            depois=depois,
            ip=ctx.get("ip"),
            user_agent=ctx.get("user_agent"),
            endpoint=ctx.get("endpoint"),
            metodo_http=ctx.get("method"),
            usuario_id=ctx.get("usuario_id"),
            empresa_id=ctx.get("empresa_id"),
            payload=payload,
        )

    @staticmethod
    def sanitizar_payload(payload: Any) -> Any:
        """Remove campos sensíveis recursivamente em dict/list."""

        if payload is None:
            return None

        if isinstance(payload, datetime):
            dt = payload
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")

        if isinstance(payload, (bytes, bytearray)):
            return None

        if isinstance(payload, dict):
            out: Dict[str, Any] = {}
            for k, v in payload.items():
                if k is None:
                    continue
                lk = str(k).lower()
                if lk in SENSITIVE_FIELDS:
                    continue
                out[k] = AuditoriaService.sanitizar_payload(v)
            return out

        if isinstance(payload, list):
            return [AuditoriaService.sanitizar_payload(i) for i in payload]

        # escalares: mantém
        return payload

    @staticmethod
    def capturar_contexto() -> Dict[str, Any]:
        return capturar_request_context()

    @staticmethod
    def registrar_evento(
        *,
        acao: str,
        entidade: str,
        entidade_id: Optional[int],
        dados_antes: Optional[Dict[str, Any]] = None,
        dados_depois: Optional[Dict[str, Any]] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
        metodo_http: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        empresa_id: Optional[int] = None,
        usuario_id: Optional[int] = None,
        colaborador_id: Optional[int] = None,
        criado_em_utc: Optional[datetime] = None,
    ) -> None:
        ctx = AuditoriaService.capturar_contexto()

        empresa_id = empresa_id if empresa_id is not None else ctx.get("empresa_id")
        usuario_id = usuario_id if usuario_id is not None else ctx.get("usuario_id")
        ip = ip if ip is not None else ctx.get("ip")
        user_agent = user_agent if user_agent is not None else ctx.get("user_agent")
        endpoint = endpoint if endpoint is not None else ctx.get("endpoint")

        # metodo_http não existe como coluna; guardamos em payload/dados
        meta = {
            "metodo_http": metodo_http,
            "endpoint": endpoint,
        }

        # payload deve ser sanitizado
        dados_payload = payload if payload is not None else meta
        dados_payload = AuditoriaService.sanitizar_payload(dados_payload)

        antes = AuditoriaService.sanitizar_payload(dados_antes) if dados_antes is not None else None
        depois = AuditoriaService.sanitizar_payload(dados_depois) if dados_depois is not None else None

        # O model atual usa colunas: dados_antes/dados_depois, acao/entidade/entidade_id
        log = AuditoriaLog(
            empresa_id=empresa_id if empresa_id is not None else 0,
            usuario_id=usuario_id,
            colaborador_id=colaborador_id,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            dados_antes={"meta": dados_payload, **(antes or {})} if (antes or payload is not None) else None,
            dados_depois={"meta": dados_payload, **(depois or {})} if (depois or payload is not None) else None,
            ip=ip,
            user_agent=user_agent,
            criado_em=criado_em_utc or datetime.now(timezone.utc).replace(tzinfo=None),
        )

        db.session.add(log)

    @staticmethod
    def registrar_login(
        *,
        sucesso: bool,
        motivo: Optional[str] = None,
        login_informado: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
        metodo_http: Optional[str] = None,
        empresa_id: Optional[int] = None,
        usuario_id: Optional[int] = None,
    ) -> None:
        # Mantido no mesmo padrão de auditoria; acesso_log já existe em modelo separado.
        # Para aderir ao objetivo, usamos registrar_evento com entidade="AUTH".
        dados_depois: Dict[str, Any] = {
            "sucesso": bool(sucesso),
        }
        if sucesso:
            dados_depois.update({"motivo": None, "login_informado": login_informado})
        else:
            dados_depois.update({"motivo": motivo, "login_informado": login_informado})

        AuditoriaService.registrar_evento(
            acao="LOGIN_SUCESSO" if sucesso else "LOGIN_FALHA",
            entidade="AUTH",
            entidade_id=None,
            dados_antes=None,
            dados_depois=dados_depois,
            ip=ip,
            user_agent=user_agent,
            endpoint=endpoint,
            metodo_http=metodo_http,
            empresa_id=empresa_id,
            usuario_id=usuario_id,
        )

    @staticmethod
    def registrar_operacao(
        *,
        acao: str,
        entidade: str,
        entidade_id: Optional[int],
        antes: Optional[Any],
        depois: Optional[Any],
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
        metodo_http: Optional[str] = None,
        usuario_id: Optional[int] = None,
        empresa_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        # serializa antes/depois com safe_model_to_dict se forem modelos
        antes_dict = None
        depois_dict = None

        if antes is not None:
            if hasattr(antes, "__table__"):
                antes_dict = safe_model_to_dict(antes)
            elif isinstance(antes, dict):
                antes_dict = antes
            else:
                antes_dict = {"value": AuditoriaService.sanitizar_payload(antes)}

        if depois is not None:
            if hasattr(depois, "__table__"):
                depois_dict = safe_model_to_dict(depois)
            elif isinstance(depois, dict):
                depois_dict = depois
            else:
                depois_dict = {"value": AuditoriaService.sanitizar_payload(depois)}

        AuditoriaService.registrar_evento(
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            dados_antes=antes_dict,
            dados_depois=depois_dict,
            ip=ip,
            user_agent=user_agent,
            endpoint=endpoint,
            metodo_http=metodo_http,
            payload=payload,
            empresa_id=empresa_id,
            usuario_id=usuario_id,
        )

