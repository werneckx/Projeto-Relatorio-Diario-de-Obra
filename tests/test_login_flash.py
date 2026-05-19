def test_login_flash_shown_on_invalid_credentials(client, app, obter_csrf):
    from app import db
    from app.models.empresa import Empresa
    from app.models.usuario import Usuario, Colaborador, Papel, UsuarioPapel

    # Criar usuário admin
    with app.app_context():
        empresa = Empresa(nome="FlashTest", ativo=True)
        db.session.add(empresa)
        db.session.flush()

        colaborador = Colaborador(
            nome="Flash Teste",
            empresa_id=empresa.id,
            tipo="PROPRIO",
            ativo=True,
        )
        db.session.add(colaborador)
        db.session.flush()

        papel = Papel(nome="ADMIN", ativo=True, is_system=True)
        db.session.add(papel)
        db.session.flush()

        usuario = Usuario(
            email="flash@test.com",
            empresa_id=empresa.id,
            colaborador_id=colaborador.id,
            ativo=True,
        )
        usuario.set_senha("Senha123")
        db.session.add(usuario)
        db.session.flush()

        usuario_papel = UsuarioPapel(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            papel_id=papel.id,
            ativo=True,
        )
        db.session.add(usuario_papel)
        db.session.commit()

    # Obtem csrf e faz POST inválido
    token = obter_csrf('/auth/login')
    resp = client.post(
        '/auth/login',
        data={'email': 'flash@test.com', 'senha': 'wrong', 'csrf_token': token},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"E-mail, senha ou status de usu\xc3\xa1rio inv\xc3\xa1lido." in resp.data
