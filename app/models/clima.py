from app import db

class Clima(db.Model):
    __tablename__ = "clima"

    id = db.Column(db.Integer, primary_key=True)
    # Assumindo que este é o campo usado para a busca genérica no auth.py
    nome = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f'<Clima {self.nome}>'