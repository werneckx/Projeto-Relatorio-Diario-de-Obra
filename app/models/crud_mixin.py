from __future__ import annotations

from datetime import datetime
from typing import Optional


class CRUDMixin:
    """Mixin de persistência com Soft Delete e suporte a restore (futuro)."""

    def soft_delete(self, usuario=None, motivo: Optional[str] = None):
        """Exclusão lógica padronizada.

        Regras:
        - Se houver campo `ativo`, torna FALSE.
        - Se houver `deletado_em` e `deletado_por`, preenche.
        - Se houver `modificado_por`, atualiza com o usuario.

        Observação: não faz commit/rollback aqui. Quem chama deve estar em
        contexto transacional.
        """

        if hasattr(self, "ativo"):
            # Assume que o campo é boolean.
            setattr(self, "ativo", False)

        if hasattr(self, "deletado_em"):
            setattr(self, "deletado_em", datetime.utcnow())

        if hasattr(self, "deletado_por") and usuario is not None:
            setattr(self, "deletado_por", getattr(usuario, "id", usuario))

        if hasattr(self, "modificado_por") and usuario is not None:
            setattr(self, "modificado_por", getattr(usuario, "id", usuario))

        if hasattr(self, "modificado_em"):
            # Alguns models usam onupdate no DB, mas aqui deixamos explícito.
            # Se o model não tiver coluna, o hasattr evita quebra.
            setattr(self, "modificado_em", datetime.utcnow())

    def restore(self, usuario=None):
        """Restauração futura (não exigida agora), quando existir `ativo`."""

        if hasattr(self, "ativo"):
            setattr(self, "ativo", True)

        if hasattr(self, "deletado_em"):
            # Mantém compatibilidade; se quiser rastrear restauração, pode ser estendido.
            setattr(self, "deletado_em", None)

        if hasattr(self, "deletado_por"):
            setattr(self, "deletado_por", None)

        if hasattr(self, "modificado_por") and usuario is not None:
            setattr(self, "modificado_por", getattr(usuario, "id", usuario))

        if hasattr(self, "modificado_em"):
            setattr(self, "modificado_em", datetime.utcnow())


def supports_soft_delete(obj) -> bool:
    return hasattr(obj, "ativo") or hasattr(obj, "deletado_em") or hasattr(obj, "deletado_por")

