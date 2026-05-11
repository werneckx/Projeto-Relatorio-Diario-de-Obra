from app.routes.auth_common import *

#######################################################################################################
####################################################################################################### MEU PERFIL (Todos os users)
#######################################################################################################

@auth_bp.get("/meu-perfil")
@login_required
def meu_perfil():
    user = Usuario.query.get(session.get("user_id"))
    return render_template("configuracoes_perfil.html", current_user=user)

@auth_bp.post("/atualizar-meu-perfil")
@login_required
def atualizar_perfil():
    user = Usuario.query.get(session.get("user_id"))
    nome = request.form.get("nome")
    telefone = request.form.get("telefone") 
    departamento = request.form.get("departamento") 
    
    if user:
        user.nome = nome
        user.departamento = departamento
        if hasattr(user, 'telefone'): user.telefone = telefone
        try:
            db.session.commit()
            session["user_name"] = user.nome
            flash("Perfil atualizado com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")
    return redirect(url_for("auth.meu_perfil"))

@auth_bp.post("/alterar-minha-senha")
@login_required
def alterar_minha_senha():
    senha_atual = request.form.get("senha_atual")
    nova_senha = request.form.get("nova_senha")
    confirmar_senha = request.form.get("confirmar_senha")
    
    if nova_senha != confirmar_senha:
        flash("A confirmação da nova senha não confere.", "danger")
        return redirect(url_for("auth.meu_perfil"))
        
    user = Usuario.query.get(session.get("user_id"))
    if not user or not check_password_hash(user.senha, senha_atual):
        flash("A senha atual está incorreta.", "danger")
        return redirect(url_for("auth.meu_perfil"))
        
    try:
        user.set_senha(nova_senha)
        db.session.commit()
        flash("Senha alterada com sucesso! Use a nova senha no próximo login.", "success")
    except Exception:
        db.session.rollback()
        flash("Erro ao alterar senha.", "danger")
    return redirect(url_for("auth.meu_perfil"))
