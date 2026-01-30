# Arquivo: app/utils/security_pdf.py
import io
import secrets
import pikepdf

def travar_edicao_pdf(pdf_bytes_original):
    """
    Recebe os bytes do PDF e aplica criptografia para impedir:
    - Cópia de texto
    - Edição de formulários
    - Alteração de conteúdo
    Mantém apenas a permissão de Impressão.
    """
    
    # 1. Gera uma senha forte e aleatória (32 caracteres)
    # Ninguém saberá essa senha, tornando impossível desbloquear a edição.
    senha_mestra = secrets.token_hex(32) 
    
    # 2. Abre o PDF na memória
    buffer_saida = io.BytesIO()
    
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes_original)) as pdf:
            
            # 3. Define as permissões (O que PODE fazer)
            # Tudo que não estiver aqui, será bloqueado.
            permissoes = pikepdf.Permissions(
                print_highres=True,       # Permite impressão em alta qualidade
                extract=False,            # BLOQUEIA copiar texto (Ctrl+C)
                modify_other=False,       # BLOQUEIA editar texto/imagens
                modify_annotation=False,  # BLOQUEIA comentários/notas
                modify_form=False,        # BLOQUEIA preencher formulários
                modify_assembly=False     # BLOQUEIA juntar/separar páginas
            )
            
            # 4. Salva o novo PDF com a criptografia
            # user="": Usuário abre sem senha
            # owner=senha_mestra: Só edita quem tiver essa senha (ninguém tem)
            pdf.save(
                buffer_saida,
                encryption=pikepdf.Encryption(
                    user="", 
                    owner=senha_mestra,
                    allow=permissoes
                )
            )
            
        return buffer_saida.getvalue()
        
    except Exception as e:
        print(f"Erro ao travar PDF: {e}")
        # Em caso de erro crítico, retorna o original (melhor que quebrar o sistema)
        # mas idealmente deve-se tratar o erro.
        return pdf_bytes_original