from app import create_app, db
from app.models.usuario import Usuario

app = create_app()
with app.app_context():
    users = Usuario.query.all()
    for u in users:
        # Resetting passwords to 'admin123' as a temporary measure
        u.set_senha("admin123")
        print(f"Password reset for: {u.email}")
    db.session.commit()
    print("All passwords reset successfully.")
