from flask import session

from app.services.config_service import ConfigService
from app.models.configuracao import ConfigDefinicao


def test_list_and_edit_empresa_config(client, app, db_session, empresa, usuario):
    # Cria definição
    defin = ConfigDefinicao(chave='test.boolean', descricao='Teste boolean', tipo='BOOLEAN', valor_padrao='false')
    db_session.add(defin)
    db_session.commit()

    # Garante permissões necessárias para o papel do usuário
    from app.models.usuario import Permissao, PapelPermissao
    papel = usuario.papeis[0]
    perm_config = Permissao(empresa_id=empresa.id, chave='config.manage', descricao='Gerenciar configs', is_system=False, ativo=True)
    perm_empresa = Permissao(empresa_id=empresa.id, chave='empresa.manage', descricao='Gerenciar empresa', is_system=False, ativo=True)
    db_session.add_all([perm_config, perm_empresa])
    db_session.flush()
    db_session.add(PapelPermissao(empresa_id=empresa.id, papel_id=papel.id, permissao_id=perm_config.id, ativo=True))
    db_session.add(PapelPermissao(empresa_id=empresa.id, papel_id=papel.id, permissao_id=perm_empresa.id, ativo=True))
    usuario.troca_senha_obrigatoria = False
    db_session.commit()

    # Simula sessão de usuário logado
    with client.session_transaction() as sess:
        sess['user_id'] = usuario.id
        sess['empresa_id'] = empresa.id

    # GET lista via UI de empresa
    resp = client.get('/auth/empresa', follow_redirects=True)
    assert resp.status_code == 200

    # Save via AJAX API
    resp = client.post('/auth/empresa/api_config', json={'chave': defin.chave, 'valor': 'true'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True

    # Valor aplicado
    with app.app_context():
        val = ConfigService.obter_valor(empresa_id=empresa.id, chave=defin.chave)
        assert val is True


def test_api_update_empresa_config(client, app, db_session, empresa, usuario):
    defin = ConfigDefinicao(chave='test.api', descricao='Teste API', tipo='STRING', valor_padrao='default')
    db_session.add(defin)
    db_session.commit()

    from app.models.usuario import Permissao, PapelPermissao
    papel = usuario.papeis[0]
    perm = Permissao(empresa_id=empresa.id, chave='config.manage', descricao='Gerenciar configs', is_system=False, ativo=True)
    db_session.add(perm)
    db_session.flush()
    db_session.add(PapelPermissao(empresa_id=empresa.id, papel_id=papel.id, permissao_id=perm.id, ativo=True))
    usuario.troca_senha_obrigatoria = False
    db_session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = usuario.id
        sess['empresa_id'] = empresa.id

    resp = client.post('/auth/empresa/api_config', json={'chave': defin.chave, 'valor': 'abc'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['valor'] == 'abc'

    with app.app_context():
        assert ConfigService.obter_valor(empresa_id=empresa.id, chave=defin.chave) == 'abc'


def test_admin_blueprint_access_with_global_admin_role(client, db_session, empresa, usuario):
    from app.models.usuario import Papel, Permissao, PapelPermissao, UsuarioPapel

    papel_global = Papel(nome='ADMIN', empresa_id=None, ativo=True, is_system=True)
    db_session.add(papel_global)
    db_session.flush()

    perm = Permissao(
        empresa_id=None,
        chave='config.manage',
        descricao='Gerenciar configs',
        is_system=True,
        ativo=True,
    )
    db_session.add(perm)
    db_session.flush()

    db_session.add(PapelPermissao(
        empresa_id=None,
        papel_id=papel_global.id,
        permissao_id=perm.id,
        ativo=True,
    ))
    db_session.add(UsuarioPapel(
        empresa_id=empresa.id,
        usuario_id=usuario.id,
        papel_id=papel_global.id,
        ativo=True,
    ))
    usuario.is_system_record = True
    usuario.troca_senha_obrigatoria = False
    db_session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = usuario.id
        sess['empresa_id'] = empresa.id

    resp = client.get('/admin/configuracoes')
    assert resp.status_code == 200


def test_admin_blueprint_denies_company_admin_without_system_flag(client, db_session, empresa, usuario):
    from app.models.usuario import Papel, Permissao, PapelPermissao, UsuarioPapel

    papel_global = Papel(nome='ADMIN', empresa_id=None, ativo=True, is_system=True)
    db_session.add(papel_global)
    db_session.flush()

    perm = Permissao(
        empresa_id=None,
        chave='config.manage',
        descricao='Gerenciar configs',
        is_system=True,
        ativo=True,
    )
    db_session.add(perm)
    db_session.flush()

    db_session.add(PapelPermissao(
        empresa_id=None,
        papel_id=papel_global.id,
        permissao_id=perm.id,
        ativo=True,
    ))
    db_session.add(UsuarioPapel(
        empresa_id=empresa.id,
        usuario_id=usuario.id,
        papel_id=papel_global.id,
        ativo=True,
    ))
    usuario.is_system_record = False
    usuario.troca_senha_obrigatoria = False
    db_session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = usuario.id
        sess['empresa_id'] = empresa.id

    resp = client.get('/admin/configuracoes')
    assert resp.status_code == 302
    assert '/auth/inicio' in resp.location


def test_edit_obra_config(client, app, db_session, empresa1, usuario_empresa1):
    defin = ConfigDefinicao(chave='test.int', descricao='Teste int', tipo='INT', valor_padrao='5')
    db_session.add(defin)
    db_session.commit()

    # Cria cliente e obra válidos (cliente requerido por obra)
    from app.models.cliente import Cliente
    from app.models.obra import Obra
    cli = Cliente(razao_social='Cli Test', cnpj='00.000.000/0001-00', empresa_id=empresa1.id, ativo=True)
    db_session.add(cli)
    db_session.flush()
    obr = Obra(nome='Obra Test', empresa_id=empresa1.id, status=1, criado_por=usuario_empresa1.id, cliente_id=cli.id)
    db_session.add(obr)
    db_session.commit()

    # Garante permissão
    from app.models.usuario import Papel, Permissao, PapelPermissao, UsuarioPapel
    papel = usuario_empresa1.papeis[0]
    perm = Permissao(empresa_id=empresa1.id, chave='config.manage', descricao='Gerenciar configs', is_system=False, ativo=True)
    db_session.add(perm)
    db_session.flush()
    db_session.add(PapelPermissao(empresa_id=empresa1.id, papel_id=papel.id, permissao_id=perm.id, ativo=True))

    # Cria role global do tipo ADMIN para permitir acesso ao blueprint /admin
    papel_global = Papel(nome='ADMIN', empresa_id=None, ativo=True, is_system=True)
    db_session.add(papel_global)
    db_session.flush()
    db_session.add(UsuarioPapel(empresa_id=empresa1.id, usuario_id=usuario_empresa1.id, papel_id=papel_global.id, ativo=True))
    usuario_empresa1.is_system_record = True
    usuario_empresa1.troca_senha_obrigatoria = False
    db_session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = usuario_empresa1.id
        sess['empresa_id'] = empresa1.id
        sess['obra_id'] = obr.id

    # GET obra configs
    resp = client.get(f'/admin/obras/{obr.id}/configuracoes')
    assert resp.status_code == 200
    assert b'test.int' in resp.data

    # POST edit obra config
    resp = client.post(f'/admin/obras/{obr.id}/configuracoes/{defin.chave}/editar', data={'valor': '10'}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        val = ConfigService.obter_valor(empresa_id=empresa1.id, obra_id=obr.id, chave=defin.chave)
        assert val == 10
