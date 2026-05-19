from __future__ import annotations

from typing import Optional

from app.models.configuracao import EmpresaConfig, ObraConfig


class ConfigService:
    """Leitura de configurações por empresa/obra (sem commit/rollback)."""

    @staticmethod
    def obter_valor(
        *,
        empresa_id: int,
        chave: str,
        obra_id: Optional[int] = None,
    ) -> Optional[str]:
        if obra_id is not None:
            cfg_obra = ObraConfig.query.filter_by(
                empresa_id=empresa_id,
                obra_id=obra_id,
                chave=chave,
            ).first()
            if cfg_obra and cfg_obra.valor is not None:
                return cfg_obra.valor

        cfg_emp = EmpresaConfig.query.filter_by(
            empresa_id=empresa_id,
            chave=chave,
        ).first()
        if cfg_emp and cfg_emp.valor is not None:
            return cfg_emp.valor

        return None

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

