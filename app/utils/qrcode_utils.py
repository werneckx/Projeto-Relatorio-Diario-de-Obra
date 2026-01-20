import qrcode
import io
import base64

def gerar_qrcode_b64(data):
    """
    Gera um QR Code a partir de uma string (data) e retorna
    uma string base64 pronta para ser usada em tags <img src="..."> HTML.
    """
    # Configuração do QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    
    # Adiciona os dados (URL)
    qr.add_data(data)
    qr.make(fit=True)

    # Cria a imagem
    img = qr.make_image(fill_color="black", back_color="white")

    # Salva em memória (buffer) em vez de arquivo físico
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    
    # Converte para Base64
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return img_str