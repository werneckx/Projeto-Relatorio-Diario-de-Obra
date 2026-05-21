from __future__ import annotations

from typing import Optional
import time

from app.models.configuracao import EmpresaConfig, ObraConfig, ConfigDefinicao


class ConfigService:
    """Leitura de configurações por empresa/obra (sem commit/rollback)."""

    @staticmethod
    def obter_valor(
        *,
        empresa_id: int,
        chave: str,
        obra_id: Optional[int] = None,
    ) -> Optional[str]:
        # 1) Verifica configuração específica da obra
        if obra_id is not None:
            cfg_obra = ObraConfig.query.filter_by(
                empresa_id=empresa_id,
                obra_id=obra_id,
                chave=chave,
            ).first()
            if cfg_obra and cfg_obra.valor is not None:
                definicao = ConfigDefinicao.query.filter_by(chave=chave).first()
                return definicao.cast_value(cfg_obra.valor) if definicao else cfg_obra.valor

        # 2) Verifica configuração da empresa
        cfg_emp = EmpresaConfig.query.filter_by(
            empresa_id=empresa_id,
            chave=chave,
        ).first()
        if cfg_emp and cfg_emp.valor is not None:
            definicao = ConfigDefinicao.query.filter_by(chave=chave).first()
            return definicao.cast_value(cfg_emp.valor) if definicao else cfg_emp.valor

        # 3) Fallback para valor padrão definido em config_definicoes (sistema)
        definicao = ConfigDefinicao.query.filter_by(chave=chave).first()
        if definicao:
            return definicao.cast_value(definicao.valor_padrao)

        return None

    @staticmethod
    def obter_mapa_config(
        *,
        empresa_id: int,
        obra_id: Optional[int] = None,
    ) -> dict:
        """Retorna um dicionário com todas as chaves de configuração e seus valores
        aplicados considerando a ordem: Obra -> Empresa -> Sistema (valor_padrao).
        """
        # Simple in-memory TTL cache to reduce DB hits. Invalidate on write.
        key = (empresa_id, obra_id)
        TTL = 60  # seconds

        if not hasattr(ConfigService, "_CACHE"):
            ConfigService._CACHE = {}

        cache = ConfigService._CACHE
        now = time.time()
        if key in cache:
            ts, data = cache[key]
            if now - ts < TTL:
                return data

        mapa = {}
        definicoes = ConfigDefinicao.query.all()
        for d in definicoes:
            mapa[d.chave] = ConfigService.obter_valor(empresa_id=empresa_id, obra_id=obra_id, chave=d.chave)

        cache[key] = (now, mapa)
        return mapa

    @staticmethod
    def clear_cache_for_empresa(empresa_id: int):
        # Deprecated alias: clear all cache keys for the empresa
        ConfigService.clear_cache(empresa_id=empresa_id, obra_id=None)

    @staticmethod
    def clear_cache(empresa_id: int, obra_id: Optional[int] = None):
        """Invalidate cache for a company, optionally scoped to a specific obra.

        If obra_id is None, clears all cache entries belonging to the empresa.
        If obra_id is provided, clears only that empresa:obra key.
        """
        if not hasattr(ConfigService, "_CACHE"):
            return
        if obra_id is None:
            keys = [k for k in ConfigService._CACHE.keys() if k[0] == empresa_id]
            for k in keys:
                ConfigService._CACHE.pop(k, None)
        else:
            key = (empresa_id, obra_id)
            ConfigService._CACHE.pop(key, None)

    @staticmethod
    def obter_timezone(
        *,
        empresa_id: int,
        obra_id: Optional[int] = None,
    ) -> str:
        tz = ConfigService.obter_valor(
            empresa_id=empresa_id,
            obra_id=obra_id,
            chave="timezone",
        )
        return (tz or "UTC").strip()

