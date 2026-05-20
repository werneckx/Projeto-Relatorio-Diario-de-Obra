from datetime import datetime

from app import db
from app.models.rdo import RDO, RDOAprovacao, RDOMaoObra
from sqlalchemy import func


class BIService:
    @staticmethod
    def produtividade(empresa_id):
        total_rdos = RDO.query.filter_by(empresa_id=empresa_id, ativo=True).count()
        total_horas = db.session.query(func.coalesce(func.sum(RDOMaoObra.quantidade_horas), 0)).filter(
            RDOMaoObra.empresa_id == empresa_id,
            RDOMaoObra.ativo == True,
        ).scalar() or 0

        return {
            "total_rdos": int(total_rdos),
            "total_horas": float(total_horas),
            "media_horas_por_rdo": float(total_horas) / total_rdos if total_rdos else 0.0,
        }

    @staticmethod
    def sla(empresa_id):
        pendentes = RDOAprovacao.query.filter_by(
            empresa_id=empresa_id,
            status='PENDENTE',
            ativo=True,
        ).all()
        agora = datetime.utcnow()
        atrasados = [ap for ap in pendentes if ap.criado_em and (agora - ap.criado_em).total_seconds() > 24 * 3600]

        return {
            "pendentes": len(pendentes),
            "pendentes_atrasados": len(atrasados),
            "percentual_atraso": float(len(atrasados)) / len(pendentes) * 100 if pendentes else 0.0,
        }

    @staticmethod
    def lead_time(empresa_id):
        aprovadas = RDOAprovacao.query.filter(
            RDOAprovacao.empresa_id == empresa_id,
            RDOAprovacao.status == 'APROVADO',
            RDOAprovacao.ativo == True,
            RDOAprovacao.data_aprovacao.isnot(None),
            RDOAprovacao.criado_em.isnot(None),
        ).all()
        horas = [
            (ap.data_aprovacao - ap.criado_em).total_seconds() / 3600.0
            for ap in aprovadas
            if ap.data_aprovacao and ap.criado_em
        ]
        return {
            "aprovadas": len(horas),
            "lead_time_medio_horas": float(sum(horas) / len(horas)) if horas else 0.0,
        }

    @staticmethod
    def historico_operacional(empresa_id):
        resultados = db.session.query(
            RDO.status,
            func.count(RDO.id),
        ).filter(
            RDO.empresa_id == empresa_id,
            RDO.ativo == True,
        ).group_by(RDO.status).all()
        return {status: count for status, count in resultados}

    @classmethod
    def indicadores(cls, empresa_id):
        return {
            "produtividade": cls.produtividade(empresa_id),
            "sla": cls.sla(empresa_id),
            "lead_time": cls.lead_time(empresa_id),
            "historico_operacional": cls.historico_operacional(empresa_id),
        }
