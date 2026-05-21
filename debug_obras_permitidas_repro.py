from app import create_app, db
from app.models.usuario import Usuario, Papel, UsuarioPapel
from app.models.empresa import Empresa
from app.models.obra import Obra

app = create_app({
    'TESTING': True,
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    'WTF_CSRF_ENABLED': False,
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
})

with app.app_context():
    db.create_all()
    emp = Empresa(nome='E', ativo=True)
    db.session.add(emp)
    db.session.commit()
    pap = Papel(nome='Admin', empresa_id=emp.id, ativo=True)
    usr = Usuario(empresa_id=emp.id, email='u', senha_hash='x', ativo=True)
    db.session.add_all([pap, usr])
    db.session.flush()
    usuario_papel = UsuarioPapel(empresa_id=emp.id, usuario_id=usr.id, papel_id=pap.id, ativo=True)
    db.session.add(usuario_papel)
    db.session.commit()
    obr = Obra(nome='Obra', empresa_id=emp.id, status=1, criado_por=usr.id, cliente_id=0)
    db.session.add(obr)
    db.session.commit()
    print('Before assign', usr.obras_alocadas)
    usr.obras_permitidas = [obr]
    print('After assign', usr.obras_alocadas)
    try:
        db.session.commit()
        print('Committed OK')
    except Exception as exc:
        print('COMMIT FAILED', type(exc), exc)
        db.session.rollback()
    from sqlalchemy import text
    print('Objects in obra_usuario', db.session.execute(text('SELECT * FROM obra_usuario')).fetchall())
    db.session.delete(usr)
    try:
        db.session.commit()
        print('Deleted user OK')
    except Exception as exc:
        print('DELETE FAILED', type(exc), exc)
        db.session.rollback()
