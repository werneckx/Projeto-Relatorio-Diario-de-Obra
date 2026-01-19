import os
import pathlib
from datetime import datetime
from flask import current_app, render_template
from app.models.lista_opcoes import Clima, Equipamento, MaoObra, TagOcorrencia
from app.models.rdo import RDO

try:
    from weasyprint import HTML
except ImportError:
    HTML = None

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

    # Caminhos absolutos do sistema de arquivos
    raw_upload_folder = os.path.join(static_folder, 'uploads', 'rdo')
    raw_assinatura_folder = os.path.join(static_folder, 'uploads', 'assinaturas')
    raw_logo_path = os.path.join(static_folder, 'logo', 'logo.png')

    # CONVERSÃO PARA URI (Compatível com Windows e Linux)
    # pathlib.Path(...).as_uri() transforma "C:\pasta\arquivo.jpg" em "file:///C:/pasta/arquivo.jpg"
    upload_folder_uri = pathlib.Path(raw_upload_folder).as_uri()
    assinatura_folder_uri = pathlib.Path(raw_assinatura_folder).as_uri()
    
    mao_de_obra_options = [{"id": m.id, "nome": m.nome} for m in MaoObra.query.all()]
    equipamentos_options = [{"id": e.id, "nome": e.nome} for e in Equipamento.query.all()]
    tags_options = [{"id": t.id, "nome": t.nome} for t in TagOcorrencia.query.all()]
    
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
        clima=Clima.query.all(),
        upload_folder=upload_folder_uri,       # Caminho URI para fotos
        assinatura_folder=assinatura_folder_uri, # Caminho URI para assinaturas
        data_geracao=data_geracao              # Variável nova para o rodapé
    )

    # 4. Converter HTML para Bytes PDF
    pdf_file = HTML(string=html_string, base_url=static_folder).write_pdf()

    return pdf_file