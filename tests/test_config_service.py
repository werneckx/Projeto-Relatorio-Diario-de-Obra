from app.services.config_service import ConfigService
from app.models.configuracao import ConfigDefinicao, EmpresaConfig, ObraConfig
from app.models.obra import Obra
from app import db


def test_obter_valor_fallback_definicao(empresa, db_session):
    # Cria definição com valor padrão
    d = ConfigDefinicao(chave='test.fallback', descricao='Teste fallback', tipo='STRING', valor_padrao='padrao')
    db.session.add(d)
    db.session.commit()

    val = ConfigService.obter_valor(empresa_id=empresa.id, chave='test.fallback')
    assert val == 'padrao'


def test_obter_valor_empresa_e_obra_sobrescreve(empresa, db_session):
    # Definicao padrao
    d = ConfigDefinicao(chave='test.heranca', descricao='Teste heranca', tipo='STRING', valor_padrao='sistema')
    db.session.add(d)
    db.session.commit()

    # Valor na empresa
    ec = EmpresaConfig(empresa_id=empresa.id, chave='test.heranca', valor='valor_empresa')
    db.session.add(ec)
    db.session.commit()

    # Criar cliente e obra local
    from app.models.cliente import Cliente
    cli = Cliente(empresa_id=empresa.id, razao_social='Cliente Teste', nome_fantasia='Cli', cnpj='00.000.000/0001-00', ativo=True)
    db.session.add(cli)
    db.session.commit()

    obr = Obra(nome='Obra Teste', empresa_id=empresa.id, cliente_id=cli.id, ativo=True)
    db.session.add(obr)
    db.session.commit()

    # Valor na obra (deve sobrescrever)
    oc = ObraConfig(empresa_id=empresa.id, obra_id=obr.id, chave='test.heranca', valor='valor_obra')
    db.session.add(oc)
    db.session.commit()

    # Sem obra_id -> empresa
    v_emp = ConfigService.obter_valor(empresa_id=empresa.id, chave='test.heranca')
    assert v_emp == 'valor_empresa'

    # Com obra_id -> obra
    v_obra = ConfigService.obter_valor(empresa_id=empresa.id, obra_id=obr.id, chave='test.heranca')
    assert v_obra == 'valor_obra'


def test_obter_mapa_config_retorna_chaves(empresa, db_session):
    d1 = ConfigDefinicao(chave='mapa.a', descricao='A', tipo='STRING', valor_padrao='A')
    d2 = ConfigDefinicao(chave='mapa.b', descricao='B', tipo='BOOLEAN', valor_padrao='true')
    db.session.add_all([d1, d2])
    db.session.commit()

    # Criar cliente e obra local
    from app.models.cliente import Cliente
    cli = Cliente(empresa_id=empresa.id, razao_social='Cliente Teste 2', nome_fantasia='Cli2', cnpj='11.111.111/0001-11', ativo=True)
    db.session.add(cli)
    db.session.commit()

    obr = Obra(nome='Obra Teste 2', empresa_id=empresa.id, cliente_id=cli.id, ativo=True)
    db.session.add(obr)
    db.session.commit()

    mapa = ConfigService.obter_mapa_config(empresa_id=empresa.id, obra_id=obr.id)
    assert 'mapa.a' in mapa and 'mapa.b' in mapa
    assert mapa['mapa.a'] == 'A'
    assert mapa['mapa.b'] is True
