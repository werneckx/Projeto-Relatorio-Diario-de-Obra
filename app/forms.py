from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, PasswordField
from wtforms.validators import DataRequired, Optional


class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(message="Informe seu e-mail.")])
    senha = PasswordField("Senha", validators=[DataRequired(message="Informe sua senha.")])  # Password field


class RdoForm(FlaskForm):
    obra_id = StringField("Obra", validators=[DataRequired(message="Selecione a obra.")])
    data_rdo = StringField("Data do RDO", validators=[DataRequired(message="Informe a data do relatório.")])
    clima_manha = StringField("Clima Manhã", validators=[Optional()])
    clima_tarde = StringField("Clima Tarde", validators=[Optional()])
    csrf_token = HiddenField()
