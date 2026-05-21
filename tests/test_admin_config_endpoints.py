from flask import session

from app.services.config_service import ConfigService
from app.models.configuracao import ConfigDefinicao


def test_list_and_edit_empresa_config(client, app, db_session, empresa, usuario):
    # Cria definição
    defin = ConfigDefinicao(chave='test.boolean', descricao='Teste boolean', tipo='BOOLEAN', valor_padrao='false')
    db_session.add(defin)
    db_session.commit()

    # Garante permissão 'config.manage' para o papel do usuário
    from app.models.usuario import Permissao, PapelPermissao
    papel = usuario.papeis[0]
    perm = Permissao(empresa_id=empresa.id, chave='config.manage', descricao='Gerenciar configs', is_system=False, ativo=True)
    db_session.add(perm)
    db_session.flush()
    db_session.add(PapelPermissao(empresa_id=empresa.id, papel_id=papel.id, permissao_id=perm.id, ativo=True))
    db_session.commit()

    # Simula sessão de usuário logado
    with client.session_transaction() as sess:
        sess['user_id'] = usuario.id
        sess['empresa_id'] = empresa.id

    # GET lista
    resp = client.get('/admin/configuracoes')
    assert resp.status_code == 200
    assert b'test.boolean' in resp.data

    # POST editar
    resp = client.post(f'/admin/configuracoes/{defin.chave}/editar', data={'valor': 'true'}, follow_redirects=True)
    assert resp.status_code == 200
    # Valor aplicado
    with app.app_context():
        val = ConfigService.obter_valor(empresa_id=empresa.id, chave=defin.chave)
        assert val is True


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
    from app.models.usuario import Permissao, PapelPermissao
    papel = usuario_empresa1.papeis[0]
    perm = Permissao(empresa_id=empresa1.id, chave='config.manage', descricao='Gerenciar configs', is_system=False, ativo=True)
    db_session.add(perm)
    db_session.flush()
    db_session.add(PapelPermissao(empresa_id=empresa1.id, papel_id=papel.id, permissao_id=perm.id, ativo=True))
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
