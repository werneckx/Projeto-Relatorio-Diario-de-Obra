from app.routes.auth_common import *

@auth_bp.get("/gerar-pdf/<int:rdo_id>")
@login_required
def gerar_pdf_rdo_view(rdo_id):
    # SECURITY: Verificar se usuário tem acesso a este RDO
    rdo = RDO.query.get_or_404(rdo_id)
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
        abort(403) # Forbidden

    pdf_content = render_rdo_pdf(rdo_id) 
    try:
        pdf_content = travar_edicao_pdf(pdf_content)
    except Exception as e:
        print(f"Erro ao aplicar segurança no PDF: {e}")
    
    response = make_response(pdf_content)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"{rdo.data.strftime('%d-%m-%Y')} - RDO#{rdo_id} - {rdo.obra.nome if rdo.obra else 'Obra'}.pdf"
    response.headers['Content-Disposition'] = f'inline; filename={filename}'
    
    return response

@auth_bp.get("/gerar-pdf-compacto/<int:rdo_id>")
@login_required
def gerar_pdf_rdo_compacto_view(rdo_id):
    # SECURITY: Verificar scope
    rdo = RDO.query.get_or_404(rdo_id)
    scope_ids = get_user_scope_ids()
    if scope_ids is not None and rdo.obra_id not in scope_ids:
        abort(403)

    pdf_content = render_rdo_pdf_compact(rdo_id)
    pdf_content = travar_edicao_pdf(pdf_content)
    
    response = make_response(pdf_content)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"RDO_Compacto_{rdo_id}_Bloqueado.pdf"
    response.headers['Content-Disposition'] = f'inline; filename={filename}'
    
    return response

#######################################################################################################
####################################################################################################### RDO (Gestão)
#######################################################################################################

#######################################################################################################
####################################################################################################### EASTER EGG
#######################################################################################################

@auth_bp.get("/dev-access")
def creator_secret():
    perfil = {
        "nome": "Edson Rodrigues",
        "role": "Fullstack Developer & Tech Planner",
        "stack": ["Python", "Microsoft 365", "SQL", "JavaScript", "Java", "HTML/CSS"],
        "projetos": ["Sistema RDO", "Automação de Relatórios", "Dashboard Interativo"],
        "local": "São Paulo, SP",
        "status": "Construindo o futuro, linha por linha.",
        "links": {
            "linkedin": "https://www.linkedin.com/in/edson-rodrigues-5a1a46345/",
            "github": "https://github.com/werneckx", 
            "instagram": "https://instagram.com/werneckx", 
            "email": "mailto:er4273270@gmail.com"
        }
    }
    return render_template("documentos/criador.html", dev=perfil)

#######################################################################################################
####################################################################################################### VALIDAÇÃO PUBLICA (PÚBLICO)
#######################################################################################################

def normalizar_texto(texto):
    if not texto: return ""
    nfkd_form = unicodedata.normalize('NFKD', str(texto))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()

def extrair_dados_pdf_fitz(pdf_bytes):
    if not fitz: return []
    dados = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            palavras = page.get_text("words")
            for p in palavras:
                text_norm = normalizar_texto(p[4])
                if not text_norm: continue
                dados.append({
                    'text': text_norm,
                    'text_raw': p[4],
                    'page': i,
                    'rect': fitz.Rect(p[0], p[1], p[2], p[3])
                })
    except Exception as e: print(f"Erro extração fitz: {e}")
    return dados

def gerar_diff_visual(dados_orig, dados_up):
    diff_cards = []
    rects_to_highlight_orig = []
    rects_to_highlight_up = []
    
    textos_orig = [d['text'] for d in dados_orig]
    textos_up = [d['text'] for d in dados_up]
    
    matcher = difflib.SequenceMatcher(None, textos_orig, textos_up)
    
    ignore_list = ["criado:", "modificado:", "impressão:", "gerado", "id:", "hash:", "ip:", "rev."]
    def eh_ignoravel(t): return any(ign in t.lower() for ign in ignore_list)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal': continue
        frag_orig_list = [dados_orig[x]['text_raw'] for x in range(i1, i2)]
        frag_up_list = [dados_up[x]['text_raw'] for x in range(j1, j2)]
        frag_orig_str = " ".join(frag_orig_list)
        frag_up_str = " ".join(frag_up_list)
        if eh_ignoravel(frag_orig_str) or eh_ignoravel(frag_up_str): continue
        if frag_orig_str.replace(" ", "") == frag_up_str.replace(" ", ""): continue
        
        if tag == 'replace':
            diff_cards.append({'tipo': 'alteracao', 'original': frag_orig_str, 'enviado': frag_up_str})
            rects_to_highlight_orig.extend([d for d in dados_orig[i1:i2]])
            rects_to_highlight_up.extend([d for d in dados_up[j1:j2]])
        elif tag == 'delete':
            diff_cards.append({'tipo': 'remocao', 'original': frag_orig_str, 'enviado': ""})
            rects_to_highlight_orig.extend([d for d in dados_orig[i1:i2]])
        elif tag == 'insert':
            diff_cards.append({'tipo': 'adicao', 'original': "", 'enviado': frag_up_str})
            rects_to_highlight_up.extend([d for d in dados_up[j1:j2]])
            
    return diff_cards, rects_to_highlight_orig, rects_to_highlight_up

def aplicar_highlights(pdf_bytes, lista_dados, color):
    if not fitz or not lista_dados: return pdf_bytes
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        por_pagina = {}
        for item in lista_dados:
            p = item['page']
            if p not in por_pagina: por_pagina[p] = []
            por_pagina[p].append(item['rect'])
        for page_idx, rects in por_pagina.items():
            if page_idx < len(doc):
                page = doc[page_idx]
                for r in rects:
                    annot = page.add_highlight_annot(r)
                    annot.set_colors(stroke=color)
                    annot.update()
        output = BytesIO()
        doc.save(output)
        return output.getvalue()
    except Exception: return pdf_bytes

@auth_bp.route("/validar-documento", methods=["GET", "POST"])
def validar_documento_publico():
    from app.models.rdo import RDO, RDOAprovacao
    try:
        from pypdf import PdfReader
        from io import BytesIO
    except ImportError: PdfReader = None
    
    resultado = None
    erro = None
    hash_buscado = ""
    status_auditoria = "pendente"
    diff_data = [] 
    pdf_original_b64 = None
    pdf_enviado_b64 = None
    texto_pdf_enviado = ""
    bytes_original = None
    bytes_enviado = None

    if request.method == 'POST':
        if 'pdf_file' in request.files and request.files['pdf_file'].filename != '':
            if PdfReader is None:
                 erro = "Erro interno: Biblioteca 'pypdf' não instalada."
            else:
                try:
                    arquivo_pdf = request.files['pdf_file']
                    bytes_enviado = arquivo_pdf.read()
                    stream_enviado = BytesIO(bytes_enviado)
                    leitor = PdfReader(stream_enviado)
                    for pagina in leitor.pages: texto_pdf_enviado += pagina.extract_text() + "\n"
                    texto_norm = normalizar_texto(texto_pdf_enviado)
                    match = re.search(r"id:\s*([a-fa-f0-9]{64})", texto_norm)
                    if match: hash_buscado = match.group(1)
                    else:
                        match_solto = re.search(r"([a-fa-f0-9]{64})", texto_norm)
                        if match_solto: hash_buscado = match_solto.group(1)
                        else: erro = "Código de autenticidade (Hash) não encontrado no arquivo."
                    pdf_enviado_b64 = base64.b64encode(bytes_enviado).decode('utf-8')
                except Exception as e: erro = f"Erro ao processar arquivo: {str(e)}"

    if hash_buscado:
        assinatura = RDOAprovacao.query.filter_by(hash=hash_buscado).first()
        if assinatura:
            if assinatura.status == 'APROVADO':
                rdo = assinatura.rdo
                if texto_pdf_enviado:
                    try:
                        bytes_original = render_rdo_pdf(rdo.id)
                        if fitz:
                            dados_orig = extrair_dados_pdf_fitz(bytes_original)
                            dados_up = extrair_dados_pdf_fitz(bytes_enviado)
                            diff_data, rects_orig, rects_up = gerar_diff_visual(dados_orig, dados_up)
                            if rects_orig: bytes_original = aplicar_highlights(bytes_original, rects_orig, (1, 0, 0))
                            if rects_up: bytes_enviado = aplicar_highlights(bytes_enviado, rects_up, (0, 1, 0))
                        
                        status_auditoria = "aprovado" if len(diff_data) == 0 else "alerta"
                        pdf_original_b64 = base64.b64encode(bytes_original).decode('utf-8')
                        pdf_enviado_b64 = base64.b64encode(bytes_enviado).decode('utf-8')
                    except Exception as e:
                        print(f"Erro Auditoria: {e}")
                        status_auditoria = "erro"
                
                resultado = {
                    "valido": True,
                    "rdo_id": rdo.id_sequencial,
                    "revisao": rdo.id_revisao,
                    "obra": rdo.obra.nome,
                    "data_rdo": rdo.data,
                    "assinante_nome": assinatura.aprovador.nome,
                    "assinante_papel": assinatura.aprovador.papel,
                    "data_assinatura": assinatura.data_aprovacao,
                    "hash_completo": assinatura.hash,
                    "status_auditoria": status_auditoria,
                    "diff_data": diff_data,
                    "pdf_original_b64": pdf_original_b64,
                    "pdf_enviado_b64": pdf_enviado_b64
                }
            else: erro = "Este documento foi invalidado no sistema."
        else: erro = "Código de autenticidade (Hash) não encontrado na base de dados."

    return render_template("documentos/public_validacao.html", resultado=resultado, erro=erro, hash_buscado=hash_buscado)
    
