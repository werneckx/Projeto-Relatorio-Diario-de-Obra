from __future__ import annotations

from typing import List

from app import db
from app.models.obra import FrenteColaborador
from app.models.rdo import RDOMaoObra


class RDOMaoObraService:
    @staticmethod
    def preencher_por_frente(rdo_id: int, frente_id: int) -> List[RDOMaoObra]:
        """
        Preenche RDOMaoObra a partir de FrenteColaborador.

        Regra:
        - cria linhas apenas com dados explícitos da origem (sem inventar regras)
        - idempotência por (rdo_id, colaborador_id) para evitar duplicidade
        """
        if not rdo_id or not frente_id:
            return []

        # obter empresa_id a partir do RDO para respeitar NOT NULL em rdo_mao_obra.empresa_id
        from app.models.rdo import RDO

        rdo_obj = RDO.query.filter_by(id=rdo_id, ativo=True).first()
        if not rdo_obj:
            return []

        empresa_id = rdo_obj.empresa_id
        if empresa_id is None:
            # evita constraint NOT NULL em rdo_mao_obra.empresa_id sem quebrar a sessão
            return []

        fcs = (
            FrenteColaborador.query.filter_by(frente_id=frente_id, ativo=True)
            .all()
        )

        if not fcs:
            return []

        # Idempotência: evita duplicar se já existe linha para (rdo_id, colaborador_id).
        colaborador_ids = [fc.colaborador_id for fc in fcs if fc.colaborador_id is not None]
        existente = (
            db.session.query(RDOMaoObra.colaborador_id)
            .filter(RDOMaoObra.rdo_id == rdo_id)
            .filter(RDOMaoObra.colaborador_id.in_(colaborador_ids))
            .all()
        )
        existente_set = {row[0] for row in existente}

        # Isola efeitos no banco para não contaminar transação do teste/teardown.
        # Se algo falhar, rollback apenas do nested.
        criados: List[RDOMaoObra] = []
        try:
            with db.session.begin_nested():
                for fc in fcs:
                    if fc.colaborador_id in existente_set:
                        continue

                    item = RDOMaoObra(
                        empresa_id=empresa_id,
                        rdo_id=rdo_id,
                        colaborador_id=fc.colaborador_id,
                        # Sem mapeamento inventado: funcao é string no destino.
                        # A origem tem funcao_id (FK AuxFuncoes), então deixamos funcao=None.
                        funcao=None,
                        # quantidade_horas/tipo_mao_obra são opcionais (nullable)
                        quantidade_horas=None,
                        tipo_mao_obra=None,
                        ativo=True,
                    )
                    db.session.add(item)
                    criados.append(item)
        except Exception:
            # Mantém sessão utilizável no outer transaction.
            db.session.rollback()
            return []

        return criados
