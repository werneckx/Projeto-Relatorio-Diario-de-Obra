import os
from flask import render_template, current_app, url_for
from weasyprint import HTML, CSS
from app.models.rdo import RDO
from app.models.obra import Obra
from app.models.usuario import Usuario
from app.models.lista_opcoes import Clima
from app.models.rdo import Fotos, RDOMaoObra

def render_rdo_pdf(rdo_id):
    """
    Renderiza o HTML do RDO e converte para bytes de PDF usando WeasyPrint.
    """
    # 1. Buscar dados do Banco
    rdo = RDO.query.get_or_404(rdo_id)
    
    # Carregar relacionamentos auxiliares para passar ao Template
    # (Caso o seu Model não tenha relationships configurados automaticamente)
    obra = Obra.query.get(rdo.id_obra)
    usuario = Usuario.query.get(rdo.id_usuario)
    clima_manha = Clima.query.get(rdo.id_climas_manha)
    clima_tarde = Clima.query.get(rdo.id_climas_tarde)
    fotos = Fotos.query.filter_by(id_rdo=rdo.id).all()
    
    # Ajuste manual para objetos dentro do RDO se o template exigir 'rdo.obra.nome'
    # Se seus models já tiverem relationships (db.relationship), isso não é necessário.
    rdo.obra = obra
    rdo.usuario = usuario
    rdo.clima_manha_obj = clima_manha
    rdo.clima_tarde_obj = clima_tarde
    
    # Tratamento de Fotos: Converter caminho relativo para absoluto para o PDF engine
    # O WeasyPrint precisa de caminhos absolutos de disco ou URLs completas
    processed_fotos = []
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'rdo')
    
    for f in fotos:
        # Cria um objeto simples para o template com o caminho absoluto do arquivo
        # O template deve usar 'file://' + path para renderização local segura
        abs_path = os.path.join(upload_folder, f.arquivo)
        processed_fotos.append({
            'url': f"file://{abs_path}", 
            'filename': f.comentario or "Sem legenda"
        })

    # Caminho das fontes para o CSS
    fonts_path = os.path.join(current_app.root_path, 'static', 'fonts')

    # Logo da empresa (exemplo)
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    logo_url = f"file://{logo_path}" if os.path.exists(logo_path) else None

    # 2. Renderizar o HTML como String
    html_string = render_template(
        'modelo_rdo.html',
        rdo=rdo,
        rdo_fotos=processed_fotos,
        fonts_path=f"file://{fonts_path}", # Importante para carregar @font-face
        logo=logo_url
    )

    # 3. Converter para PDF
    # base_url é definido para que o WeasyPrint ache CSS/Imagens relativos se necessário
    pdf_bytes = HTML(string=html_string, base_url=current_app.static_folder).write_pdf()

    return pdf_bytes