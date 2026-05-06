import os
import pathlib
from datetime import datetime
from flask import current_app, render_template,url_for
from app.models.auxiliares import AuxClima, AuxEquipamentos, AuxFuncoes, AuxTagOcorrencia
from app.models.rdo import RDO
from app.utils.qrcode_utils import gerar_qrcode_b64

try:
    from weasyprint import HTML
except ImportError:
    HTML = None

def _build_mao_obra_tipo_map():
    """Mapeia o nome da mão de obra ao tipo cadastrado."""
    tipo_por_nome = {}

    for mao in AuxFuncoes.query.all():
        nome_normalizado = (mao.descricao or "").strip().lower()
        if nome_normalizado and nome_normalizado not in tipo_por_nome:
            tipo_por_nome[nome_normalizado] = mao.tipo or ""

    return tipo_por_nome

def render_rdo_pdf(rdo_id):
    """
    Busca os dados do RDO, prepara os caminhos das imagens e renderiza o PDF.
    """
    if not HTML:
        raise Exception("A biblioteca WeasyPrint não está instalada. Execute: pip install WeasyPrint")

    # 1. Buscar o objeto RDO pelo ID
    rdo = RDO.query.get_or_404(rdo_id)

    # 2. Configurar caminhos absolutos e convertê-los para URI (file:///)
    static_folder = current_app.static_folder
    url_visualizacao = url_for('auth.visualizar_rdo', rdo_id=rdo.id, _external=True)
    
    # 2. Gerar a imagem base64
    qr_code_b64 = gerar_qrcode_b64(url_visualizacao)

    # Caminhos absolutos do sistema de arquivos
    raw_upload_folder = os.path.join(static_folder, 'uploads', 'rdo')
    raw_assinatura_folder = os.path.join(static_folder, 'uploads', 'assinaturas')
    raw_logo_path = os.path.join(static_folder, 'logo', 'logo.png')

    # CONVERSÃO PARA URI (Compatível com Windows e Linux)
    # pathlib.Path(...).as_uri() transforma "C:\pasta\arquivo.jpg" em "file:///C:/pasta/arquivo.jpg"
    upload_folder_uri = pathlib.Path(raw_upload_folder).as_uri()
    assinatura_folder_uri = pathlib.Path(raw_assinatura_folder).as_uri()
    
    mao_de_obra_options = [{"id": m.id, "nome": m.descricao} for m in AuxFuncoes.query.all()]
    mao_obra_tipo_map = _build_mao_obra_tipo_map()
    equipamentos_options = [{"id": e.id, "nome": e.descricao} for e in AuxEquipamentos.query.all()]
    tags_options = [{"id": t.id, "nome": t.descricao} for t in AuxTagOcorrencia.query.all()]
    
    # Tratamento do Logo
    if os.path.exists(raw_logo_path):
        logo_path_uri = pathlib.Path(raw_logo_path).as_uri()
    else:
        logo_path_uri = None

    # NOVO: Data de geração para o rodapé do template Enterprise
    data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M')

    # 3. Renderizar o Template HTML
    html_string = render_template(
        'modelo_rdo.html',
        rdo=rdo,
        logo_path=logo_path_uri,
        clima=AuxClima.query.all(),
        upload_folder=upload_folder_uri,       # Caminho URI para fotos
        assinatura_folder=assinatura_folder_uri, # Caminho URI para assinaturas
        data_geracao=data_geracao,             # Variável nova para o rodapé
        qr_code_b64=qr_code_b64,
        tipo_mao_obra_options=mao_de_obra_options,
        mao_obra_tipo_map=mao_obra_tipo_map,
    )

    # 4. Converter HTML para Bytes PDF
    pdf_file = HTML(string=html_string, base_url=static_folder).write_pdf()

    return pdf_file

def render_rdo_pdf_compact(rdo_id):
    """
    Busca os dados do RDO, prepara os caminhos das imagens e renderiza o PDF.
    """
    if not HTML:
        raise Exception("A biblioteca WeasyPrint não está instalada. Execute: pip install WeasyPrint")

    # 1. Buscar o objeto RDO pelo ID
    rdo = RDO.query.get_or_404(rdo_id)

    # 2. Configurar caminhos absolutos e convertê-los para URI (file:///)
    static_folder = current_app.static_folder
    url_visualizacao = url_for('auth.visualizar_rdo', rdo_id=rdo.id, _external=True)
    
    # 2. Gerar a imagem base64
    qr_code_b64 = gerar_qrcode_b64(url_visualizacao)

    # Caminhos absolutos do sistema de arquivos
    raw_upload_folder = os.path.join(static_folder, 'uploads', 'rdo')
    raw_assinatura_folder = os.path.join(static_folder, 'uploads', 'assinaturas')
    raw_logo_path = os.path.join(static_folder, 'logo', 'logo.png')

    # CONVERSÃO PARA URI (Compatível com Windows e Linux)
    # pathlib.Path(...).as_uri() transforma "C:\pasta\arquivo.jpg" em "file:///C:/pasta/arquivo.jpg"
    upload_folder_uri = pathlib.Path(raw_upload_folder).as_uri()
    assinatura_folder_uri = pathlib.Path(raw_assinatura_folder).as_uri()
    
    mao_de_obra_options = [{"id": m.id, "nome": m.descricao} for m in AuxFuncoes.query.all()]
    equipamentos_options = [{"id": e.id, "nome": e.descricao} for e in AuxEquipamentos.query.all()]
    tags_options = [{"id": t.id, "nome": t.descricao} for t in AuxTagOcorrencia.query.all()]
    
    # Tratamento do Logo
    if os.path.exists(raw_logo_path):
        logo_path_uri = pathlib.Path(raw_logo_path).as_uri()
    else:
        logo_path_uri = None

    # NOVO: Data de geração para o rodapé do template Enterprise
    data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M')

    # 3. Renderizar o Template HTML
    html_string = render_template(
        'modelo_rdo_compacta.html',
        rdo=rdo,
        logo_path=logo_path_uri,
        clima=AuxClima.query.all(),
        upload_folder=upload_folder_uri,       # Caminho URI para fotos
        assinatura_folder=assinatura_folder_uri, # Caminho URI para assinaturas
        data_geracao=data_geracao,             # Variável nova para o rodapé
        qr_code_b64=qr_code_b64
    )

    # 4. Converter HTML para Bytes PDF
    pdf_file = HTML(string=html_string, base_url=static_folder).write_pdf()

    return pdf_file
