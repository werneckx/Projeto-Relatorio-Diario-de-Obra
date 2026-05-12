# Arquitetura do Nosde System RDO

Esta documentação descreve a arquitetura do projeto, os principais componentes e o fluxo do sistema.

## Visão geral

O Nosde System RDO é uma aplicação web construída com Flask seguindo uma arquitetura modular simples:

- `app/__init__.py` define a aplicação e inicializa as extensões.
- `app/routes/auth.py` concentra as rotas de autenticação, criação e gerenciamento de RDOs.
- `app/models/` contém as entidades SQLAlchemy que representam o domínio do sistema.
- `app/forms.py` define formulários com Flask-WTF e habilita CSRF.
- `app/templates/` contém os templates Jinja2 usados pelo frontend.
- `app/static/` armazena CSS, imagens, uploads e arquivos públicos.
- `app/utils/` contém utilitários como geração de PDF e QR Code.

## Camadas do sistema

### 1. Apresentação

- `app/templates/`: páginas HTML renderizadas no servidor.
- `app/static/`: estilos, scripts e mídia estática.
- O arquivo `base.html` centraliza o layout, a navegação e as mensagens flash.

### 2. Controle

- `app/routes/auth.py`: lida com as requisições HTTP e coordena a criação, edição, visualização e exclusão de RDOs.
- Rotas também cuidam de login, logout, recuperação de senha, gerenciamento de usuários e cadastros auxiliares.
- A proteção de rota é feita com decorators de `login_required` e `role_required`.

### 3. Domínio / Persistência

- `app/models/usuario.py`: usuário, hash de senha, perfis, acesso a obras e logs de acesso.
- `app/models/obra.py`: obras, frentes de trabalho e relacionamentos com usuários.
- `app/models/rdo.py`: registros de RDO, fotos, atividades, equipamentos, ocorrências e assinaturas.
- `app/models/empresa.py`: dados da empresa / cliente, com potencial para isolar multi-tenancy.
- `app/models/lista_opcoes.py`: tabelas auxiliares como clima, mão de obra, equipamentos e tags.

## Extensões e configuração

- `Flask-SQLAlchemy`: ORM principal para persistência.
- `Flask-Migrate`: migrações de banco de dados via Alembic.
- `Flask-Login`: gerenciamento de sessão de usuário.
- `Flask-WTF`: formulários e proteção CSRF.
- `python-dotenv`: carregamento de configurações via `.env`.

A configuração do app está em `config.py` e inclui:

- `SECRET_KEY`
- conexão MySQL via `mysql+mysqlconnector`
- ativação de CSRF e cookies seguros
- diretórios padrão para upload e arquivos gerados

## Fluxo de criação de RDO

1. Usuário acessa o formulário de criação/edição de RDO.
2. O formulário é enviado para `auth.py` em `/gerar-rdo`.
3. O backend valida dados com `Flask-WTF` e processa campos de data, clima, mão de obra, atividades, equipamentos e ocorrências.
4. Fotos são recebidas, redimensionadas e comprimidas com Pillow antes de serem salvas em `static/uploads/rdo`.
5. O RDO é persistido no banco e as assinaturas iniciais são criadas no workflow.
6. A resposta retorna ao usuário com uma mensagem flash indicando sucesso ou falha.

## Considerações de segurança

- Senhas são armazenadas como hash com Werkzeug.
- Todas as rotas que alteram estado usam proteção CSRF.
- Cookies de sessão são configurados como `HttpOnly` e `SameSite=Lax`.
- A aplicação carrega segredos via `.env` e não deve versionar esse arquivo.
- Soft delete de RDOs permite recuperação caso um relatório seja excluído por engano.

## Estrutura de diretórios atual

```text
.
├── .env.example
├── .gitignore
├── ARCHITECTURE.md
├── README.md
├── app
│   ├── __init__.py
│   ├── forms.py
│   ├── models
│   │   ├── empresa.py
│   │   ├── lista_opcoes.py
│   │   ├── obra.py
│   │   ├── rdo.py
│   │   ├── usuario.py
│   │   └── __init__.py
│   ├── routes
│   │   ├── auth.py
│   │   └── __init__.py
│   ├── templates
│   ├── static
│   └── utils
├── config.py
├── migrations
├── requirements.txt
├── run.py
└── data
```

## Próximas evoluções sugeridas

- estabelecer um `service layer` em `app/services/`
- adicionar API JSON REST separada do frontend renderizado
- implementar dashboard analítico de obras e RDOs
- suportar tema claro/escuro
- tornar o app um PWA para uso offline
- isolar multi-tenancy por `empresa_id` em todas as tabelas
