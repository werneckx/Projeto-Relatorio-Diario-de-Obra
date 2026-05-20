import csv
import io
from datetime import datetime

from flask import make_response, render_template, request, send_file
from weasyprint import HTML
from openpyxl import Workbook


def _format_filename(prefix: str, extension: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"


def build_csv_bytes(headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return buffer.getvalue().encode("utf-8-sig")


def build_xlsx_bytes(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)

    for row in rows:
        sheet.append(["" if value is None else value for value in row])

    for column_cells in sheet.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        column_letter = column_cells[0].column_letter
        sheet.column_dimensions[column_letter].width = min(50, length + 2)

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def render_pdf_from_template(template_name, **context):
    html = render_template(template_name, **context)
    base_url = request.base_url
    return HTML(string=html, base_url=base_url).write_pdf()


def make_csv_response(headers, rows, prefix="export"):
    data = build_csv_bytes(headers, rows)
    filename = _format_filename(prefix, "csv")
    response = make_response(data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    return response


def make_xlsx_response(headers, rows, prefix="export"):
    xlsx_bytes = build_xlsx_bytes(headers, rows)
    filename = _format_filename(prefix, "xlsx")
    return send_file(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


def make_pdf_response(template_name, context, prefix="export"):
    pdf_bytes = render_pdf_from_template(template_name, **context)
    filename = _format_filename(prefix, "pdf")
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    return response
