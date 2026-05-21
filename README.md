# Nosde System RDO

Aplicacao web em Flask para gestão de Relatórios Diários de Obra (RDO), com recursos de autenticação, compressão de imagens, geração de PDF, assinaturas digitais, controle de acesso, auditoria completa e workflow de aprovação configurável.

## Recursos principais

- **Autenticação** com Flask-Login e recuperação de senha segura
- **Multiempresa** (multi-tenant): isolamento completo de dados por empresa
- **RBAC** (Role-Based Access Control): controle de permissões granular por papel
- **Workflow de Aprovação** configurável com etapas sequenciais ou paralelas
- **Auditoria Completa**: logs detalhados de todas as operações críticas
- **Sessões de Usuário**: rastreamento de login/logout e detecção de sessões expiradas
- **Soft Delete**: exclusão lógica com histórico preservado
- **Upload de Arquivos**: rastreável com metadados (hash, tamanho, mime type)
- **RDO Imutável**: RDOs aprovadas não podem ser editadas, com versionamento
- **Notificações**: sistema de notificações para eventos de workflow
- **Exportações**: suporte para CSV, XLSX e PDF
- **PDF com QR Code**: geração de PDFs com código QR para verificação
- **Formulários CSRF-protegidos**: com Flask-WTF
- **Hash de senha**: com Werkzeug
- **Estrutura modular** de modelos, rotas e templates
- **Configuração por ambiente** com `.env`

---

## Stack Tecnológica

- **Backend**: Python 3.11+, Flask
- **ORM**: SQLAlchemy
- **Banco de Dados**: MySQL 8.0+, InnoDB, UTF8MB4
- **Frontend**: HTML5, CSS3, Bootstrap, Tailwind CSS, JavaScript
- **Infraestrutura**: Docker, Docker Compose, MySQL, Redis (opcional)
- **Testes**: pytest com cobertura de segurança

---

## Como Executar Localmente

### 1. Clonar o repositório e preparar ambiente

```powershell
# Windows - criar e ativar ambiente virtual
python -m venv .venv
.\.venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependências

```powershell
pip install -r requirements.txt
```

### 3. Configurar arquivo de ambiente

Copie `.env.example` para `.env`:

```bash
cp .env.example .env
```

Edite `.env` com seus valores:

```text
SECRET_KEY=gerar_uma_chave_secreta_forte_aqui
DB_USER=root
DB_PASSWORD=sua_senha_mysql
DB_NAME=dbrdo
DB_HOST=localhost
DB_PORT=3306
FLASK_ENV=development
DEBUG=True
```

**Gerar SECRET_KEY segura:**

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Criar banco de dados

```powershell
# Garantir que MySQL está rodando
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS dbrdo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 5. Executar migrações

```powershell
flask db upgrade
```

### 6. Seed de dados iniciais (opcional)

```powershell
python scripts/seed_db.py
```

Isso cria:
- Empresa "Enfil SA" com dados de exemplo
- Usuário admin: `admin@example.com` / `Senha123`
- Papéis padrão: Admin, Supervisor, Operador
- Obras e RDOs de exemplo

### 7. Iniciar a aplicação

```powershell
python run.py
```

Acesse `http://localhost:5000` no navegador.

**Credenciais padrão (após seed):**
- Email: `admin@example.com`
- Senha: `Senha123`

---

## Como Executar com Docker

### 1. Preparar arquivo de ambiente

```powershell
cp .env.example .env
# Editar .env conforme necessário
```

### 2. Build e iniciar containers

```powershell
docker compose up --build
```

A aplicação fica disponível em `http://localhost:5000`.

**Acesso ao banco de dados:**
- Dentro do Docker: `mysql://db:3306`
- Desde o Windows: `mysql://localhost:3307`

### 3. Executar migrações no Docker

```powershell
docker compose exec app flask db upgrade
```

### 4. Seed de dados iniciais

```powershell
docker compose exec app python scripts/seed_db.py
```

### 5. Parar containers

```powershell
docker compose down
```

Para remover volumes também (limpar banco):

```powershell
docker compose down -v
```

---

## Executar Testes

### Testes simples (SQLite in-memory)

```powershell
# Rodar todos os testes
pytest -v

# Rodar testes específicos
pytest tests/test_security_multiempresa.py -v
pytest tests/test_rbac.py -v
pytest tests/test_rdo_complete_flow.py -v
pytest tests/test_rdo_immutable.py -v
pytest tests/test_recovery_senha.py -v
pytest tests/test_auth_logs.py -v

# Com cobertura de código
pytest --cov=app tests/
```

### Testes contra MySQL real

```powershell
# Definir URI de teste
$env:TEST_DATABASE_URI = "mysql+pymysql://root:senha@localhost:3306/test_dbrdo"

# Executar com script SQL completo
$env:TEST_RUN_DB_SCRIPT = "1"
pytest -v
```

### Testes da branch 11 (Hardening)

**Testes de Segurança:**
```powershell
pytest tests/test_security_multiempresa.py -v  # Isolamento por empresa
pytest tests/test_rbac.py -v                    # Controle de acesso
pytest tests/test_rdo_immutable.py -v           # RDO aprovado imutável
```

**Testes de Fluxo:**
```powershell
pytest tests/test_rdo_complete_flow.py -v      # Ciclo completo de RDO
pytest tests/test_auth_logs.py -v              # Login, logout, recuperação
pytest tests/test_workflow.py -v               # Aprovações e workflow
```

**Testes de Dados:**
```powershell
pytest tests/test_auditoria.py -v              # Logs de auditoria
pytest tests/test_sessoes.py -v                # Gerenciamento de sessões
pytest tests/test_arquivos.py -v               # Upload e rastreamento
pytest tests/test_recovery_senha.py -v         # Recuperação de senha
```

---

## Estrutura de Diretórios

```
├── app/
│   ├── __init__.py                 # Factory da aplicação
│   ├── models/                     # Entidades (User, RDO, Obra, etc.)
│   ├── routes/                     # Blueprints e endpoints
│   ├── services/                   # Lógica de negócio (Workflow, Auditoria, etc.)
│   ├── forms.py                    # Formulários Flask-WTF
│   ├── middleware/                 # Middleware customizado
│   ├── templates/                  # Templates Jinja2
│   ├── static/                     # CSS, JS, imagens, uploads
│   └── utils/                      # Utilitários (PDF, QR Code, etc.)
├── tests/                          # Testes pytest
│   ├── conftest.py                 # Fixtures compartilhadas
│   ├── test_security_multiempresa.py   # Isolamento por empresa
│   ├── test_rbac.py                # Controle de acesso
│   ├── test_rdo_complete_flow.py   # Ciclo completo de RDO
│   ├── test_rdo_immutable.py       # RDO aprovado imutável
│   ├── test_recovery_senha.py      # Recuperação de senha
│   ├── test_auth_logs.py           # Logs de autenticação
│   ├── test_workflow.py            # Workflow de aprovação
│   ├── test_auditoria.py           # Auditoria
│   ├── test_sessoes.py             # Sessões
│   └── test_arquivos.py            # Upload de arquivos
├── scripts/
│   ├── seed_db.py                  # Seed de dados iniciais
│   ├── ensure_db.py                # Verificação do banco
│   ├── check_users.py              # Diagnóstico de usuários
│   └── diagnostics/                # Scripts de diagnóstico
├── data/
│   └── Script Banco de Dados.sql   # Schema SQL completo
├── docs/
│   ├── Contexto.md                 # Contexto completo do projeto
│   └── Plano de Criação-Refatoração.md  # Plano de desenvolvimento
├── config.py                        # Configuração de ambiente
├── run.py                           # Ponto de entrada
├── requirements.txt                 # Dependências Python
├── Dockerfile                       # Build da imagem Docker
├── docker-compose.yml               # Orquestração de containers
└── README.md                        # Este arquivo
```

---

## Segurança

### Multiempresa (Multi-Tenant)

- Todas as queries operacionais filtram obrigatoriamente por `empresa_id`
- Usuários só veem dados de sua empresa
- Papéis e permissões isolados por empresa

### Controle de Acesso (RBAC)

- Permissões por papel (Admin, Supervisor, Operador, etc.)
- Decorators `@login_required` e `@permission_required` em endpoints
- Menu adaptado às permissões do usuário

### Soft Delete

- Registros não são removidos fisicamente, apenas marcados `ativo=False`
- Histórico preservado para auditoria
- Queries padrão filtram `ativo=True`

### Auditoria Completa

- Log de todas as operações críticas (CREATE, UPDATE, DELETE)
- Antes/depois dos dados alterados
- IP, User-Agent, endpoint, usuário e timestamp registrados
- Integração com login, RDO, workflow e arquivos

### RDO Imutável Após Aprovação

- RDOs com status `APROVADO` não podem ser editadas
- Snapshot versionado criado no momento da aprovação
- Operações críticas bloqueadas por validação na service layer

### Recuperação de Senha Segura

- Token com entropia alta (secrets.token_urlsafe)
- Armazenado apenas como hash SHA-256 no banco
- Expiração em 24 horas
- Uma única utilização por token
- Sem exposição de token em logs

### Proteção CSRF

- Todos os formulários usam Flask-WTF csrf_token
- Validação obrigatória em POST/PUT/DELETE

### Hash de Senha

- Werkzeug.security com padrão bcrypt
- Sem armazenamento de senha em plaintext

---

## Migrações de Banco de Dados

### Criar nova migração

```powershell
flask db migrate -m "descricao da mudanca"
```

### Aplicar migrações

```powershell
flask db upgrade
```

### Reverter para versão anterior

```powershell
flask db downgrade
```

### Ver histórico

```powershell
flask db history
```

---

## Scripts Auxiliares

### Seed de dados

Cria dados de exemplo para teste:

```powershell
python scripts/seed_db.py
```

### Verificar banco

```powershell
python scripts/ensure_db.py
```

### Diagnóstico

```powershell
python scripts/diagnostics/import_check.py  # Verifica importação de models
python scripts/diagnostics/db_check.py      # Verifica conexão com banco
```

### Gerenciar usuários

```powershell
python scripts/check_users.py               # Lista usuários
python scripts/reset_user_password.py       # Reset de senha
```

---

## Configuração de Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `SECRET_KEY` | Chave secreta para sessão | `dev-key` |
| `DB_USER` | Usuário MySQL | `root` |
| `DB_PASSWORD` | Senha MySQL | `` |
| `DB_NAME` | Nome do banco | `dbrdo` |
| `DB_HOST` | Host MySQL | `localhost` |
| `DB_PORT` | Porta MySQL | `3306` |
| `FLASK_ENV` | Ambiente (development/production) | `development` |
| `DEBUG` | Debug mode (True/False) | `False` |
| `MAIL_SERVER` | Servidor de email (opcional) | `` |
| `MAIL_PORT` | Porta de email | `587` |
| `MAIL_USERNAME` | Email de envio | `` |
| `MAIL_PASSWORD` | Senha de email | `` |

---

## Troubleshooting

### Erro "NOT NULL constraint failed: id"

SQLite não gerá IDs automaticamente em alguns cenários. Use MySQL para testes:

```powershell
$env:TEST_DATABASE_URI = "mysql+pymysql://root:senha@localhost:3306/test_dbrdo"
$env:TEST_RUN_DB_SCRIPT = "1"
pytest tests/test_arquivos.py -v
```

### Erro "ModuleNotFoundError: No module named 'app'"

Certifique-se que está rodando no diretório raiz do projeto:

```powershell
cd c:\Users\edson.rodrigues\Documents\MeusProjetos\Projeto-Relatorio-Diario-de-Obra---Enfil-SA
python -m pytest tests/
```

### Erro de conexão com MySQL

Verifique que MySQL está rodando:

```powershell
# Testar conexão
mysql -u root -p -e "SELECT VERSION();"
```

### Limpar cache de migrations

```powershell
Remove-Item -Recurse app/migrations/versions/*
flask db migrate -m "reset"
flask db upgrade
```

---

## Contribuindo

1. Crie uma branch para sua feature/fix:
   ```powershell
   git checkout -b feature/minha-feature
   ```

2. Faça commits pequenos e descritivos usando Conventional Commits:
   ```
   feat(modulo): descricao da mudanca
   fix(auth): correcao de bug
   test(rdo): adicionar testes
   ```

3. Rode testes antes de fazer push:
   ```powershell
   pytest -v
   ```

4. Abra um Pull Request para revisão

---

## Roadmap

- [x] **Branch 1**: Baseline e Validação de Ambiente
- [x] **Branch 2**: Separação Inicial de Rotas
- [x] **Branch 3**: Compatibilidade com Schema Novo
- [x] **Branch 4**: Multiempresa e RBAC Real
- [x] **Branch 5**: Soft Delete e Transações
- [x] **Branch 6**: Auditoria e Sessões
- [x] **Branch 7**: Workflow de Aprovação
- [x] **Branch 8**: Notificações
- [x] **Branch 9**: Arquivos e Upload
- [x] **Branch 10**: Exportações e BI
- [x] **Branch 11**: Testes e Hardening
- [ ] **Branch 12**: Definições Customizáveis por Empresa
- [ ] **Branch 13**: Mão de Obra e Colaboradores

---

## Licença

Este projeto é licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## Contato

Para dúvidas ou sugestões, contacte o time de desenvolvimento.
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
