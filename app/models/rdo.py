from datetime import datetime
from app import db 

# Se você usar 'db.relationship' sem aspas, você deve importar as classes:
# from app.models.usuario import Usuario 
# from app.models.obra import Obra 
# from app.models.clima import Clima 


class RDO(db.Model):
    __tablename__ = 'rdo'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # -------------------------------------------------------------
    # Coluna que referencia o usuário. Chave estrangeira para 'usuarios.id'
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    
    # Relacionamentos com Clima
    climas_manha = db.Column(db.Integer, db.ForeignKey('clima.id'), nullable=True) 
    climas_tarde = db.Column(db.Integer, db.ForeignKey('clima.id'), nullable=True)

    data = db.Column(db.DateTime, default=datetime.now) 
    
    numero_sequencial = db.Column(db.Integer)
    atividades = db.Column(db.Text)
    mao_obra = db.Column(db.Text) 
    fotos_json = db.Column(db.Text)
    pdf_filename = db.Column(db.String(255), nullable=True)
    total_mo = db.Column(db.Integer)
    revisao = db.Column(db.Integer, default=0)
    status = db.Column(db.String(100))
    criador = db.Column(db.String(100))

    # -------------------------------------------------------------
    # Relacionamentos
    # -------------------------------------------------------------

    # Relacionamentos usam o NOME DA CLASSE ('Obra', 'Usuario', 'Clima')
    obra = db.relationship('Obra', backref=db.backref('rdos', lazy=True))
    
    # CORREÇÃO CRÍTICA: Explicitando a chave estrangeira (foreign_keys=[usuario_id])
    # para forçar o SQLAlchemy a encontrar a condição de junção correta,
    # resolvendo o InvalidRequestError.
    usuario = db.relationship('Usuario', 
        foreign_keys=[usuario_id], 
        backref=db.backref('rdos_criados', lazy=True)
    )
    
    clima_manha_obj = db.relationship('Clima', 
        foreign_keys=[climas_manha], 
        backref=db.backref('rdos_manha', lazy='dynamic')
    )
    
    clima_tarde_obj = db.relationship('Clima', 
        foreign_keys=[climas_tarde],
        backref=db.backref('rdos_tarde', lazy='dynamic')
    )

    # -------------------------------------------------------------
    # Métodos e Propriedades
    # -------------------------------------------------------------

    @property
    def status_text(self):
        """Traduz o nome do arquivo PNG para um status legível."""
        mapping = {
            "Aguardando Aprovação.png": "Aguardando Aprovação",
            "Aprovado.png": "Aprovado",
            "Rejeitado.png": "Rejeitado"
        }
        return mapping.get(self.status, self.status)

    def to_dict(self):
        """Serializa o RDO para um dicionário Python."""
        return {
            'id': self.id,
            'obra_id': self.obra_id,
            'usuario_id': self.usuario_id, 
            'data': self.data.isoformat() if self.data else None,
            'numero_sequencial': self.numero_sequencial,
            # Incluindo a descrição do clima no dicionário (melhor usabilidade)
            'clima_manha_nome': self.clima_manha_obj.nome if self.clima_manha_obj else None,
            'clima_tarde_nome': self.clima_tarde_obj.nome if self.clima_tarde_obj else None,
            'atividades': self.atividades,
            'mao_obra': self.mao_obra,
            'fotos_json': self.fotos_json,
            'pdf_filename': self.pdf_filename,
            'status': self.status_text, 
            'revisao': self.revisao,
            'total_mo': self.total_mo,
            'criador': self.criador,
        }
    
    def __repr__(self):
        return f'<RDO {self.id} | Obra: {self.obra_id} | Data: {self.data.strftime("%Y-%m-%d") if self.data else "N/A"}>'
    
    