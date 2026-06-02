from app.routes.auth_common import *

#######################################################################################################
####################################################################################################### Inicio (Dashboard)
#######################################################################################################

@auth_bp.get("/inicio")
@login_required
def inicio():
    hoje = date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month
    
    # SCOPING: Filtra KPIs baseados nas obras permitidas do usuário
    user_id = session.get("user_id")
    user = Usuario.query.get(user_id)
    scope_ids = None if user and user.is_admin else [o.id for o in user.obras_permitidas] if user else []

    # --- 1. KPIs PRINCIPAIS ---
    
    # Query base para Obras
    q_obras = Obra.query.filter_by(empresa_id=session.get('empresa_id'))
    if scope_ids is not None:
        q_obras = q_obras.filter(Obra.id.in_(scope_ids))
    kpi_obras = q_obras.count()
    
    # Query base para RDOs
    q_rdos = RDO.query.filter_by(ativo=True, empresa_id=session.get('empresa_id'))
    if scope_ids is not None:
        q_rdos = q_rdos.filter(RDO.obra_id.in_(scope_ids))
        
    kpi_pendentes = q_rdos.filter_by(status='PENDENTE').count()
    kpi_rdos_mes = q_rdos.filter(
        extract('year', RDO.data_rdo) == ano_atual,
        extract('month', RDO.data_rdo) == mes_atual
    ).count()
    kpi_aprovados_total = q_rdos.filter_by(status='APROVADO').filter(
        extract('year', RDO.data_rdo) == ano_atual
    ).count()
    
    # KPI 3: Efetivo Total (Hoje)
    query_efetivo = db.session.query(
        func.count(RDOMaoObra.id)
    ).join(RDO).filter(RDO.data_rdo == hoje)
    
    if scope_ids is not None:
        query_efetivo = query_efetivo.filter(RDO.obra_id.in_(scope_ids))
        
    kpi_efetivo = query_efetivo.scalar() or 0
    
    # KPI 4: Ocorrências (No Mês Atual)
    query_ocorrencias = db.session.query(func.count(RDOOcorrencia.id))\
        .join(RDO)\
        .filter(extract('year', RDO.data_rdo) == ano_atual)\
        .filter(extract('month', RDO.data_rdo) == mes_atual)
        
    if scope_ids is not None:
        query_ocorrencias = query_ocorrencias.filter(RDO.obra_id.in_(scope_ids))

    kpi_ocorrencias = query_ocorrencias.scalar() or 0

    # --- 2. DADOS PARA INTERATIVIDADE ---
    q_raw = db.session.query(RDO.id, RDO.status, RDO.data_rdo).filter(
        RDO.ativo == True,
        extract('year', RDO.data_rdo) == ano_atual
    )
    if scope_ids is not None:
        q_raw = q_raw.filter(RDO.obra_id.in_(scope_ids))
    raw_rdos = q_raw.all()
    
    dados_graficos_json = [
        {
            'status': str(rdo.status.value) if hasattr(rdo.status, 'value') else str(rdo.status), 
            'mes': rdo.data_rdo.month, 
            'data_iso': rdo.data_rdo.isoformat()
        } 
        for rdo in raw_rdos
        if rdo.data_rdo
    ]

    # --- 3. TABELA DE RESUMO (Últimos Registros) ---
    ultimos_rdos = q_rdos.order_by(RDO.data_rdo.desc(), RDO.id.desc()).limit(5).all()

    return render_template(
        "dashboard/inicio.html",
        kpi_obras=kpi_obras,
        kpi_pendentes=kpi_pendentes,
        kpi_efetivo=int(kpi_efetivo),
        kpi_ocorrencias=kpi_ocorrencias,
        ultimos_rdos=ultimos_rdos,
        dados_graficos_json=dados_graficos_json,
        kpi_rdos_mes=kpi_rdos_mes,
        kpi_aprovados_total=kpi_aprovados_total
    )
