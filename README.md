Modelo completo:

# Projeto RDO - Registro Diário de Obra

Este projeto é uma aplicação Flask para geração e gerenciamento de RDO (Registro Diário de Obra).

## 📁 Estrutura do Projeto



app/
routes/
models/
services/
templates/
static/
data/
storage/
instance/
migrations/
run.py
requirements.txt


## 🚀 Como executar o projeto

### 1. Criar ambiente virtual


python -m venv venv
source venv/in/activate # Linux
venv\Scripts\activate # Windows


### 2. Instalar dependências


pip install -r requirements.txt


### 3. Configurar variáveis de ambiente
Criar o arquivo `.env` com:



SECRET_KEY=sua_chave
DATABASE_URL=sqlite:///dbrdo.db


### 4. Inicializar o banco


flask db upgrade


### 5. Rodar a aplicação


python run.py


## 🗂 Pastas importantes

`storage/` → arquivos gerados (PDF, imagens)  
`data/` → banco de dados, backups  
`app/` → toda a aplicação Flask  

## 👨‍💻 Tecnologias

- Python + Flask
- SQLAlchemy
- Bootstrap
- MySQL ou SQLite
