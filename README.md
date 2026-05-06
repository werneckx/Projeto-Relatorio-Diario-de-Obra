# Nosde System RDO

Aplicacao web em Flask para gestao de Relatorios Diarios de Obra (RDO), com recursos de autenticacao, compressao de imagens, geracao de PDF, assinaturas digitais e controle de acesso.

## Recursos principais

- Autenticacao com Flask-Login
- Formularios com Flask-WTF e protecao CSRF
- Hash de senha com Werkzeug
- Upload de fotos com compressao via Pillow
- Soft delete de RDOs usando campo `ativo`
- Relatorios em PDF
- Estrutura modular de modelos, rotas e templates
- Configuracao por ambiente com `.env`

## Como executar

### 1. Criar ambiente virtual

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 3. Criar o arquivo de ambiente

Copie `.env.example` para `.env` e preencha os valores:

```text
SECRET_KEY=uma_chave_super_secreta_aqui
DB_USER=root
DB_PASSWORD=senha_do_banco
DB_NAME=dbrdo
DB_HOST=localhost
DB_PORT=3306
```

### 4. Executar migracoes

```powershell
flask db upgrade
```

### 5. Iniciar a aplicacao

```powershell
python run.py
```

Acesse `http://localhost:5000` no navegador.

## Como executar com Docker

Copie `.env.example` para `.env` e ajuste a senha, se necessario. O `docker-compose.yml` ja troca `DB_HOST` para `db` dentro da rede Docker.

```powershell
docker compose up --build
```

A aplicacao fica disponivel em `http://localhost:5000`. O MySQL fica acessivel no Windows em `localhost:3307` e, dentro do Docker, em `db:3306`. O banco usa volume persistente chamado `mysql_data`; uploads e PDFs gerados tambem ficam em volumes Docker.

Para preparar o banco ou criar dados iniciais:

```powershell
docker compose exec app flask db upgrade
docker compose exec app python scripts/seed_db.py
```

Scripts auxiliares:

```powershell
python scripts/ensure_db.py
python scripts/diagnostics/import_check.py
python scripts/diagnostics/db_check.py
```

## Estrutura do projeto

- `app/`
  - `__init__.py` - cria a aplicacao e inicializa extensoes
  - `routes/auth.py` - principais rotas de autenticacao e operacoes RDO
  - `models/` - entidades de banco de dados (Usuario, Obra, RDO, Empresa, etc.)
  - `forms.py` - formularios Flask-WTF
  - `templates/` - paginas HTML Jinja2
  - `static/` - arquivos publicos, CSS, imagens e uploads
  - `utils/` - utilitarios para PDF, QR Code e imagens
- `scripts/` - manutencao, seed e diagnosticos
- `config.py` - configuracoes de ambiente e banco
- `.env.example` - modelo de arquivo de ambiente
- `requirements.txt` - dependencias do Python
- `run.py` - ponto de entrada da aplicacao
- `data/` - backups ou dados adicionais
- `app/migrations/` - migracoes do banco de dados

## Notas importantes

- Nunca versionar o arquivo `.env`
- Use `.env.example` como referencia para configuracao
- Em producao, garanta que `static/uploads` fique protegido

## Dependencias principais

- Flask
- Flask-WTF
- Flask-Login
- Flask-Migrate
- Flask-SQLAlchemy
- python-dotenv
- Pillow
- qrcode[pil]
- pdfkit
- weasyprint
- reportlab
- pikepdf
- pypdf
- pymupdf
- gunicorn

## Melhorias futuras

- PWA para modo offline
- Dashboard de gestao
- Tema claro/escuro
- Multi-tenancy mais explicito
- API REST separada do frontend
