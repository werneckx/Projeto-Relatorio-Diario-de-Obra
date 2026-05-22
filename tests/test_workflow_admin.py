def test_crud_workflow_admin(client, app, db_session, empresa, usuario):
    # Garante permissão 'workflow.manage' para o papel do usuário
    from app.models.usuario import Papel, Permissao, PapelPermissao, UsuarioPapel
    papel = usuario.papeis[0]
    perm = Permissao(empresa_id=empresa.id, chave='workflow.manage', descricao='Gerenciar workflows', is_system=False, ativo=True)
    db_session.add(perm)
    db_session.flush()
    db_session.add(PapelPermissao(empresa_id=empresa.id, papel_id=papel.id, permissao_id=perm.id, ativo=True))

    papel_global = Papel(nome='ADMIN', empresa_id=None, ativo=True, is_system=True)
    db_session.add(papel_global)
    db_session.flush()
    db_session.add(UsuarioPapel(empresa_id=empresa.id, usuario_id=usuario.id, papel_id=papel_global.id, ativo=True))
    db_session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = usuario.id
        sess['empresa_id'] = empresa.id

    # Lista (vazio)
    resp = client.get('/admin/workflows')
    assert resp.status_code == 200

    # Cria novo workflow
    resp = client.post('/admin/workflows/novo', data={'nome': 'WF Test', 'descricao': 'Descrição', 'aprovacao_paralela': 'on'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Workflow criado com sucesso' in resp.data

    # Verifica listagem
    resp = client.get('/admin/workflows')
    assert b'WF Test' in resp.data

    # Obtém id (simples pesquisa no HTML)
    # Edita (pega primeiro workflow)
    from app.models.workflow import WorkflowDefinicao
    with app.app_context():
        wf = WorkflowDefinicao.query.filter_by(empresa_id=empresa.id, nome='WF Test').first()
        assert wf is not None
        wid = wf.id

    resp = client.post(f'/admin/workflows/{wid}/editar', data={'nome': 'WF Test Renomeado', 'descricao': 'D2'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Workflow atualizado com sucesso' in resp.data

    # Desativar
    resp = client.post(f'/admin/workflows/{wid}/excluir', data={}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Workflow desativado' in resp.data


def test_ajax_update_empresa_config(client, app, db_session, empresa, usuario):
    # Cria definição
    from app.models.configuracao import ConfigDefinicao
    from app.models.usuario import Permissao, PapelPermissao
    defin = ConfigDefinicao(chave='ajax.test', descricao='Ajax test', tipo='STRING', valor_padrao='x')
    db_session.add(defin)
    db_session.commit()

    # Garante permissão 'config.manage'
    papel = usuario.papeis[0]
    perm = Permissao(empresa_id=empresa.id, chave='config.manage', descricao='Gerenciar configs', is_system=False, ativo=True)
    db_session.add(perm)
    db_session.flush()
    db_session.add(PapelPermissao(empresa_id=empresa.id, papel_id=papel.id, permissao_id=perm.id, ativo=True))
    db_session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = usuario.id
        sess['empresa_id'] = empresa.id

    # Chamada AJAX
    headers = {'Content-Type': 'application/json', 'X-CSRFToken': 'token'}
    resp = client.post('/auth/empresa/api_config', json={'chave': 'ajax.test', 'valor': 'novo'}, headers=headers)
    assert resp.status_code == 200
    j = resp.get_json()
    assert j.get('ok') is True

    # Verifica valor persistido
    from app.services.config_service import ConfigService
    with app.app_context():
        v = ConfigService.obter_valor(empresa_id=empresa.id, chave='ajax.test')
        assert v == 'novo'
