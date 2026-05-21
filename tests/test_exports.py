import pytest
from datetime import date

from app import db
from app.models.rdo import RDO


def _authenticate(client, usuario):
    with client.session_transaction() as sess:
        sess['user_id'] = usuario.id
        sess['empresa_id'] = usuario.empresa_id


def test_export_lista_rdo_csv_xlsx_pdf(client, app, db_session, usuario, obra, frente_trabalho):
    rdo = RDO(
        empresa_id=usuario.empresa_id,
        obra_id=obra.id,
        frente_trabalho_id=frente_trabalho.id,
        numero_sequencial=1,
        data_rdo=date(2025, 1, 1),
        status='APROVADO',
        criado_por=usuario.id,
        ativo=True,
    )
    db_session.add(rdo)
    db_session.commit()
    usuario.obras_permitidas = [obra]
    db_session.commit()

    _authenticate(client, usuario)

    response = client.get('/auth/lista-rdo/export/csv')
    assert response.status_code == 200
    assert response.content_type.startswith('text/csv')
    assert b'APROVADO' in response.data
    assert obra.nome.encode() in response.data

    response = client.get('/auth/lista-rdo/export/xlsx')
    assert response.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in response.content_type
    assert response.data[:2] == b'PK'

    response = client.get('/auth/lista-rdo/export/pdf')
    assert response.status_code == 200
    assert response.data[:4] == b'%PDF'


def test_export_lista_obras_csv_pdf(client, app, db_session, usuario, obra):
    _authenticate(client, usuario)

    response = client.get('/auth/lista-obras/export/csv')
    assert response.status_code == 200
    assert response.content_type.startswith('text/csv')
    assert str(obra.id).encode() in response.data

    response = client.get('/auth/lista-obras/export/pdf')
    assert response.status_code == 200
    assert response.data[:4] == b'%PDF'


def test_indicadores_bi_route(client, usuario):
    with client.session_transaction() as sess:
        sess['user_id'] = usuario.id
        sess['empresa_id'] = usuario.empresa_id

    response = client.get('/auth/indicadores')
    assert response.status_code == 200
    assert b'Indicadores' in response.data
