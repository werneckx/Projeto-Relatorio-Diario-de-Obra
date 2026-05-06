from app import create_app, db
from app.models.usuario import Usuario

app = create_app()
with app.app_context():
    users = Usuario.query.all()
    for u in users:
        print(f"User: {u.email}, Hash: '{u.senha_hash}'")
