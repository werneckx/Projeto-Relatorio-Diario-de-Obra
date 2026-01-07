import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from flask import current_app
from app.models.rdo import RDO
from app.models.obra import Obra
from app.models.usuario import Usuario
from app.models.lista_opcoes import Clima
from app import db


def regenerar_pdf_rdo(rdo_id):
    """
    Gera um PDF do RDO e retorna:
    - Caminho completo do arquivo gerado
    - Nome do arquivo para download
    """

    # Busca o RDO
    rdo = RDO.query.get(rdo_id)
    if not rdo:
        raise ValueError("RDO não encontrado.")

    # Pasta onde os PDFs serão salvos
    pdf_dir = os.path.join(current_app.root_path, "static", "rdo_pdfs")
    os.makedirs(pdf_dir, exist_ok=True)

    # Nome do arquivo PDF
    pdf_filename = f"RDO_{rdo.numero_sequencial or rdo.id}_REV_{rdo.revisao or 0}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    # Criação do PDF
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    # Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "RELATÓRIO DIÁRIO DE OBRA (RDO)")

    c.setFont("Helvetica", 12)
    c.drawString(50, height - 90, f"RDO Nº: {rdo.numero_sequencial}")
    c.drawString(250, height - 90, f"Revisão: {rdo.revisao}")
    c.drawString(50, height - 120, f"Data: {rdo.data.strftime('%d/%m/%Y %H:%M')}")

    obra = Obra.query.get(rdo.obra_id)
    usuario = Usuario.query.get(rdo.usuario_id)
    clima_manha = Clima.query.get(rdo.climas_manha)
    clima_tarde = Clima.query.get(rdo.climas_tarde)

    c.drawString(50, height - 150, f"Obra: {obra.nome if obra else '---'}")
    c.drawString(50, height - 180, f"Responsável: {usuario.nome if usuario else '---'}")

    c.drawString(50, height - 210, f"Clima Manhã: {clima_manha.nome if clima_manha else '---'}")
    c.drawString(250, height - 210, f"Clima Tarde: {clima_tarde.nome if clima_tarde else '---'}")

    # Atividades executadas
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, height - 250, "Atividades do Dia:")

    c.setFont("Helvetica", 11)
    text_obj = c.beginText(50, height - 270)
    text_obj.setLeading(14)
    atividades = rdo.atividades or "Nenhuma atividade registrada."

    # Quebra de linha para textos longos
    for line in atividades.split("\n"):
        text_obj.textLine(line)

    c.drawText(text_obj)

    # Finalização
    c.showPage()
    c.save()

    return pdf_path, pdf_filename
