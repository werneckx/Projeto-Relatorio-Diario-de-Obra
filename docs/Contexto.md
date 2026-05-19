# CONTEXTO COMPLETO DO PROJETO — NOSDE SYSTEM RDO

## Visão Geral

Este projeto consiste em uma plataforma corporativa de gestão de Relatório Diário de Obra (RDO), desenvolvida em Flask, com arquitetura multiempresa (multi-tenant), controle de permissões por papéis (RBAC), workflow de aprovação configurável, auditoria completa e capacidade de expansão futura para integrações, BI, automações e clientes externos.

O sistema tem como objetivo centralizar e gerenciar operações de obras de construção civil e engenharia, permitindo o acompanhamento operacional diário das obras, equipes, equipamentos, ocorrências, produtividade, aprovações, documentação e indicadores gerenciais.

O projeto deve possuir arquitetura escalável, modular, segura e preparada para crescimento corporativo.

---

# Stack Tecnológica

## Backend

- Python
- Flask
- SQLAlchemy

## Banco de Dados

- MySQL
- InnoDB
- UTF8MB4

## Frontend

- HTML5
- CSS3
- JavaScript
- Bootstrap
- Tailwind CSS
- Templates Jinja2 responsivos

## Infraestrutura

- Docker
- Linux
- WSL2
- Ambiente preparado para cloud

---

# Arquitetura do Sistema

O sistema deve seguir arquitetura modular corporativa.

## Estrutura Esperada

```plaintext
app/
├── routes/
├── services/
├── repositories/
├── validators/
├── permissions/
├── middleware/
├── templates/
├── static/
├── models/
├── forms/
├── utils/
├── exports/
├── notifications/
├── workflow/
└── integrations/
```

---

# Regras Arquiteturais Obrigatórias

## Multiempresa (Multi-Tenant)

Todas as tabelas transacionais e operacionais devem possuir:

```sql
empresa_id
```

Nenhum usuário poderá visualizar ou manipular dados de outra empresa.

Toda consulta deve obrigatoriamente filtrar:

```python
empresa_id = current_user.empresa_id
```

---

## Soft Delete

Nenhum registro operacional deverá ser removido fisicamente.

O sistema deve utilizar:

```sql
ativo BOOLEAN DEFAULT TRUE
```

Ao excluir:

- Alterar apenas `ativo = FALSE`
- Manter rastreabilidade
- Preservar integridade histórica

---

## Auditoria

Toda operação crítica deve registrar:

- Usuário
- Data/Hora
- IP
- User Agent
- Dados antes
- Dados depois
- Entidade afetada

Tabela existente:

- `auditoria_log`

O sistema deve possuir middleware de auditoria automática.

---

# Segurança

## Requisitos Obrigatórios

- Senha com hash seguro
- CSRF Protection
- Session Management
- Controle RBAC
- Rate Limit
- Proteção contra SQL Injection
- Proteção contra XSS
- Logs de acesso
- Controle de permissões por rota
- Logout seguro
- Expiração de sessão

---

# Controle de Permissões (RBAC)

O sistema deve utilizar:

- Usuários
- Papéis
- Permissões
- Usuário Papel
- Papel Permissão

As permissões devem controlar:

- Menus
- Rotas
- Ações
- Visualização
- Edição
- Aprovação
- Exportação

## Exemplo

```python
@permission_required('rdo.create')
```

---

# Governança de Dados

Existe uma tabela central chamada:

```sql
cad_listas
```

Responsável por:

- Catálogo de tabelas
- Governança
- Integração
- Versionamento estrutural
- Rastreabilidade

---

# Modelos Existentes

## Modelos Auxiliares

- Clima
- Função
- Equipamento
- Tag de Ocorrência
- Tipo de Obra

## Auditoria

- Auditoria Log

## Empresa

- Empresa

## Cliente

- Cliente

## Fornecedor

- Fornecedor

## Obras

- Obras
- Frente de Trabalho
- Frente Colaborador
- Obra Usuário

## Usuários

- Colaborador
- Usuário
- Papel
- Permissão
- Usuário Papel
- Papel Permissão

## RDO

- RDO
- Atividades
- Equipamentos
- Mão de Obra
- Ocorrências
- Fotos
- Aprovações
- Assinaturas

## Configurações

- Configuração da Empresa
- Configuração da Obra
- Definições Globais

---

# Requisitos Gerais do Sistema

## Exportação

Todas as rotas e listagens devem permitir:

- Exportar PDF
- Exportar XLSX
- Exportar CSV
- Impressão

---

## Transações

Todas as operações críticas devem utilizar transação.

Se qualquer etapa falhar:

- Realizar rollback completo
- Não permitir alterações parciais

---

## Persistência de Formulário

Caso haja erro ao salvar:

- Manter dados preenchidos
- Exibir erros amigáveis
- Evitar perda de informações

---

## Verificação de Alteração

Ao editar registros:

- Validar se houve alteração real
- Caso não exista alteração:
  - Exibir mensagem
  - Retornar para visualização

---

## Templates

Todos os templates devem:

- Seguir padrão visual único
- Ser responsivos
- Reutilizar componentes
- Possuir acessibilidade
- Possuir IDs compatíveis com banco/model

---

# Padronização HTML

Todos os campos HTML devem possuir IDs padronizados conforme model/banco.

## Exemplos

```html
<input id="obra_nome" name="nome">

<select id="cliente_id" name="cliente_id">

<input id="hora_entrada_padrao">
```

Nunca utilizar:

```html
id="field"
id="name"
```

Objetivos:

- Automação
- Testes automatizados
- Integração com IA
- Rastreabilidade frontend

---

# Componentes Visuais

## Botões

Todos os botões devem seguir padrão único:

- Tamanho
- Fonte
- Cor
- Espaçamento
- Borda
- Ícones

## Botões Obrigatórios

- Salvar
- Editar
- Excluir
- Cancelar
- Voltar
- Aprovar
- Rejeitar
- Exportar

---

# Template Base

## Cabeçalho

Deve possuir:

- Logo da empresa
- Menu dinâmico conforme permissão
- Notificações
- Usuário logado
- Menu dropdown

---

## Menu Principal

### Início

### Relatórios

- Lista RDO
- Novo RDO

### Cadastros

- Obras
- Clientes
- Colaboradores
- Usuários
- Fornecedores

### Auxiliares

- Clima
- Função
- Equipamento
- Tag Ocorrência
- Tipo de Obra

---

# Notificações

O sistema deve possuir tabela:

```sql
notificacoes
```

## Funcionalidades

- Aprovações pendentes
- Novo RDO
- Alertas
- Rejeições
- Avisos operacionais

---

# Rodapé

Deve conter:

- Logo do sistema
- Nome da plataforma
- Versão
- Ano
- Suporte
- Privacidade
- Termos de uso

---

# Dashboard Inicial

O dashboard deve ser dinâmico conforme permissão.

## Administrador Plataforma

- Todas as empresas
- Métricas globais

## Administrador Empresa

- Obras da empresa
- Indicadores da empresa

## Administrador Obra

- Frentes
- Produtividade
- Status

## Administrador Frente

- Atividades
- Mão de obra
- Produção

---

# Requisitos Empresa

Cada empresa poderá personalizar:

- Nome
- Logo
- Ícone
- Tema
- Cores
- Workflow
- Modelo RDO

## Campos Recomendados

- tema_cor_primaria
- tema_cor_secundaria
- dark_mode
- favicon

---

# Requisitos Obras

## Campos

- Nome
- Cliente
- Tipo de Obra
- Responsável
- CNPJ
- Datas
- Endereço completo
- Jornada padrão
- Configurações

---

# Integrações

## CEP

Consulta automática via API.

## CNPJ

Possibilidade futura de integração automática.

---

# Integrações Futuras

Permitir criar programações de RDO's. Por exemplo, o planejador de uma obra sabe que uma atividade vai ser executada dia X, o sistema deverá permitir esse pré cadastramento da programação do dia para quando o usuario responsável pelo preenchimento acessar o sistema, ele poderá ver o que tem planejado e falar o que foi realizado ou não na proprio apontamento do RDO.

# Frentes de Trabalho

Cada obra:

- Possui várias frentes
- Possui equipes vinculadas a cada frente.
- Acelera preenchimento do RDO

---

# Requisitos RDO

## Status Padronizados

```sql
RASCUNHO
PENDENTE
APROVADO
REJEITADO
CANCELADO
```

---

# Workflow

Workflow configurável por:

- Empresa
- Obra
- Níveis
- Aprovadores
- SLA
- Aprovação paralela
- Rejeição

---

# Aprovação

Registrar:

- Hash
- IP
- Assinatura
- Data
- Usuário

---

# Bloqueio Pós Aprovação

RDO aprovado:

- Não pode ser editado
- Deve ser versionado

---

# Versionamento

O RDO deve possuir:

- Controle de versão
- Histórico
- Rastreabilidade

---

# Módulos Operacionais

## Atividades

- Descrição
- Status
- Observação

## Equipamentos

- Equipamento
- Quantidade
- Horas
- Status
- Motivo parada

## Mão de Obra

- Colaborador
- Função
- Horas
- Tipo
- Observação

## Ocorrências

- Tipo
- Impacto
- Paralisação
- Descrição

## Fotos

- Anexos
- Evidências
- Imagens da obra

---

# Arquivos e Documentos

Criar estrutura genérica:

```sql
arquivos
```

## Finalidade

- PDF
- Imagens
- ART
- Contratos
- Anexos
- Documentos

## Compatibilidade

- Local
- S3
- Azure
- MinIO

---

# Requisitos de Listagem

Todas as listagens devem possuir:

- Filtros
- Paginação
- Busca
- Ordenação
- Exportação
- Ações rápidas

## Ações

- Visualizar
- Editar
- Excluir

---

# Controle de Sessão

Criar estrutura para:

- Sessões ativas
- Auditoria login
- Logout remoto
- Expiração

---

# BI e Indicadores

Estrutura preparada para:

- Power BI
- Dashboards
- SLA
- Produtividade
- Lead Time
- Histórico operacional

---

# Integrações Futuras

O sistema deve estar preparado para integração com:

- Power BI
- Power Apps
- Power Automate
- UiPath
- n8n
- ERP
- APIs externas
- WhatsApp
- E-mail
- OCR
- IA

---

# Regras Globais

- Nenhum usuário acessa outra empresa
- Permissões controlam menus e rotas
- Toda operação crítica deve ser auditada
- Todo delete é lógico
- Todo RDO aprovado é imutável
- Todo upload deve ser rastreável
- Toda listagem deve exportar dados
- Todo formulário deve manter consistência visual

---

# Objetivo Final

Construir uma plataforma corporativa de gestão operacional de obras com:

- Arquitetura escalável
- Governança de dados
- Rastreabilidade completa
- Workflow corporativo
- Multiempresa
- Auditoria
- BI Ready
- Integrações futuras
- Experiência profissional
- Segurança corporativa
- Expansão modular


O sistema deve estar preparado para crescimento enterprise e evolução contínua sem necessidade de refatoração estrutural massiva.

Feito até o momento:

- Marco 1 - Base saudável concluído em 2026-05-12.
- Compatibilidade do schema novo com rotas principais e templates (Branch `fix/schema-route-compat`) aplicada.
- Verificação (2026-05-12): Branches 1, 2 e 3 revisadas em `app/routes` e `app/templates`; compatibilização inclui alias de aprovações (`rdo.assinaturas` / `ass.id_usuario`) e correção do template `app/templates/list_rdo.html` para manter navegação e filtros operacionais.
- Marco 2 - Auditoria & Sessoes (Branch `feat/auditoria-sessoes`) integradas no fluxo real de RDO:
  - `app/services/auditoria_service.py`: centralização do serviço de auditoria (sem commit/rollback), incluindo helper único `registrar_auditoria_entidade(...)`.
  - `app/routes/auth.py`: gravação de `session_uuid`/contexto de sessão e suporte a trilha de login/logout.
  - `app/routes/rdo.py`:
    - `gerar_rdo()` agora registra `UPDATE` com snapshot **before/after** determinístico (sem `locals()`).
    - `excluir_rdo()` registra `SOFT_DELETE` com snapshot **before/after** dentro da mesma transação da operação principal.
  - Validação automatizada: `python -m pytest -q` → **4 passed, 1 warning** (warning pré-existente `PytestReturnNotNoneWarning` em `test_login.py::test_login`).

## Checkpoint em 2026-05-11

### Estrutura de banco de dados

- O arquivo `data/Script Banco de Dados.sql` foi ampliado para representar a arquitetura corporativa descrita neste contexto.
- O script contempla `CREATE DATABASE`, `DROP TABLE` em ordem reversa, tabelas InnoDB e `utf8mb4`.
- Foram estruturadas as tabelas principais de:
  - `empresa`
  - `cad_listas`
  - auxiliares: `aux_clima`, `aux_funcoes`, `aux_equipamentos`, `aux_tag_ocorrencia`, `aux_tipo_obra`
  - RBAC: `usuarios`, `papeis`, `permissoes`, `usuario_papel`, `papel_permissao`
  - cadastros: `clientes`, `fornecedores`, `colaboradores`
  - obras: `obras`, `frente_trabalho`, `frente_colaborador`, `obra_usuario`
  - RDO: `rdo`, `rdo_mao_obra`, `rdo_equipamentos`, `rdo_ocorrencias`, `rdo_atividades`, `rdo_fotos`, `rdo_aprovacoes`, `rdo_assinaturas`
  - auditoria/configuracoes: `auditoria_log`, `config_definicoes`, `empresa_config`, `obra_config`
- Foram adicionadas as estruturas corporativas que faltavam:
  - `rdo_versoes`
  - `workflow_definicoes`
  - `workflow_etapas`
  - `notificacoes`
  - `arquivos`
  - `sessoes_usuario`
  - `acesso_log`
- O RDO foi preparado para os status padronizados:
  - `RASCUNHO`
  - `PENDENTE`
  - `APROVADO`
  - `REJEITADO`
  - `CANCELADO`
- O RDO recebeu campos para versionamento e bloqueio:
  - `versao`
  - `rdo_origem_id`
  - `bloqueado_em`
  - `bloqueado_por`
- A tabela `cad_listas` foi alimentada como catalogo de governanca das tabelas do sistema.
- Foram criados seeds globais de papeis, permissoes, auxiliares e configuracoes.
- Foi criada uma massa de dados demonstrativa inicial.
- Foi criada uma massa de dados corporativa completa para a empresa ficticia `Enfil Saneamento e Engenharia S.A.`, preenchendo todas as tabelas do script com dados relacionados.

### Models SQLAlchemy

- Os models existentes foram revisados e alinhados parcialmente ao novo script SQL.
- `app/models/rdo.py` foi atualizado com:
  - novos status do RDO
  - campos de versionamento
  - campos de bloqueio
  - relacionamento de RDO origem/revisoes
  - model `RDOVersao`
- `app/models/auxiliares.py` foi atualizado para permitir auxiliares globais com `empresa_id = NULL` e campo `is_system`.
- Foram criados novos models:
  - `app/models/workflow.py`
    - `WorkflowDefinicao`
    - `WorkflowEtapa`
  - `app/models/notificacao.py`
    - `Notificacao`
  - `app/models/arquivo.py`
    - `Arquivo`
  - `app/models/sessao.py`
    - `SessaoUsuario`
    - `AcessoLog`
- O arquivo `app/models/__init__.py` foi atualizado para exportar os novos models.
- Ja existem models para:
  - `CadLista`
  - `ConfigDefinicao`
  - `EmpresaConfig`
  - `ObraConfig`
  - `AuditoriaLog`

### Validacoes realizadas

- Foi feita checagem estatica do SQL para confirmar que todas as tabelas novas possuem `DROP TABLE`, `CREATE TABLE` e ao menos um `INSERT`.
- Foi feita checagem estatica dos models e exports para confirmar a presenca dos novos models.
- O script SQL completo foi executado no MySQL com sucesso em 2026-05-11, conforme validacao manual informada pelo usuario.
- A validacao real por Python/Flask nao foi concluida porque o ambiente local esta apontando para o Python da Microsoft Store e falhou ao criar processo.
- A validacao real via Docker/MySQL tambem nao foi concluida porque a sessao nao conseguiu acessar o Docker Desktop pelo pipe do Windows.

### Rotas ja existentes

- Existem dois blueprints principais:
  - `auth_bp` em `app/routes/auth.py`
  - `admin_bp` em `app/routes/admin.py`
- `auth.py` ja possui rotas para:
  - setup inicial da aplicacao
  - login
  - logout
  - recuperacao e redefinicao de senha
  - paginas institucionais: termos, privacidade e suporte
  - dashboard inicial em `/auth/inicio`
  - configuracao/visualizacao da empresa em `/auth/empresa`
  - salvar dados da empresa em `/auth/salvar-empresa`
  - geracao de PDF de RDO completo e compacto
  - criacao, edicao, visualizacao, exclusao e listagem de RDO
  - APIs auxiliares para obra, frente e clima automatico
  - workflow/assinaturas de RDO usando `RDOAprovacao`
  - aprovacao e rejeicao de RDO
  - CRUD de usuarios
  - alteracao obrigatoria de senha
  - CRUD de auxiliares:
    - clima
    - equipamentos
    - tags de ocorrencia
    - mao de obra/funcoes
  - CRUD/listagem de obras e frentes dentro do fluxo de obra
  - perfil do usuario
  - rota publica de validacao forense de documento/PDF
- `admin.py` ja possui:
  - decorator `permission_required`
  - seed programatico de roles e permissoes globais
  - CRUD administrativo de empresas
  - CRUD administrativo de fornecedores
  - API JSON de fornecedores ativos

### Templates ja existentes

- `app/templates/base.html` ja implementa:
  - layout base responsivo
  - menu desktop e mobile
  - links para RDO, cadastros, auxiliares e perfil
  - logo e icone da empresa via context processor
  - flash messages/toasts
  - rodape com suporte, privacidade e termos
  - injecao automatica de CSRF em formularios POST
- Existem templates de autenticacao e conta:
  - `login.html`
  - `setup.html`
  - `esqueci_senha.html`
  - `redefinir_senha.html`
  - `alterar_senha_obrigatoria.html`
  - `configuracoes_perfil.html`
- Existe dashboard operacional:
  - `inicio.html`
  - usa KPIs, tabela de ultimos RDOs e graficos Chart.js
- Existem telas de RDO:
  - `list_rdo.html`
  - `form_rdo.html`
  - `modelo_rdo.html`
  - `modelo_rdo_compacta.html`
  - `public_validacao.html`
  - `qr_footer.html`
- Existem telas de cadastros/auxiliares:
  - `list_usuarios.html`
  - `form_usuario.html`
  - `list_obras.html`
  - `form_obra.html`
  - `list_climas.html`
  - `form_clima.html`
  - `list_equipamentos.html`
  - `form_equipamento.html`
  - `list_tags_ocorrencias.html`
  - `form_tags_ocorrencias.html`
  - `list_mao_obra.html`
  - `form_mao_obra.html`
- Existem telas administrativas separadas:
  - `admin/base.html`
  - `admin/empresas_lista.html`
  - `admin/empresa_form.html`
  - `admin/fornecedores_lista.html`
  - `admin/fornecedor_form.html`
- Existem telas institucionais:
  - `empresa.html`
  - `termos.html`
  - `privacidade.html`
  - `suporte.html`
  - `criador.html`

### Pontos de atencao encontrados em rotas/templates

- A aplicacao ainda usa dois modelos de permissao em paralelo:
  - `role_required` em `auth.py`, baseado em papel salvo na sessao
  - `permission_required` em `admin.py`, baseado em permissoes RBAC reais
- O objetivo final deve ser padronizar em `permission_required` e permissoes como `rdo.create`, `rdo.update`, `rdo.approve`.
- Muitas queries em `auth.py` ja filtram `empresa_id`, mas ainda existem pontos que precisam revisao de multiempresa:
  - ADMIN em `lista_rdo` busca todos os RDOs ativos sem filtrar empresa.
  - alguns auxiliares/listagens consultam registros sem separar `empresa_id` e `empresa_id IS NULL`.
- O workflow visual atual usa `RDOAprovacao` e campos/aliases legados no template, como:
  - `assinaturas`
  - `id_usuario`
  - `ordem`
  - status `Pendente`, `Aprovado`, `Rejeitado`
- O schema novo tem `workflow_definicoes`, `workflow_etapas`, `rdo_aprovacoes.nivel` e status em maiusculo:
  - `PENDENTE`
  - `APROVADO`
  - `REJEITADO`
- Os templates de RDO e PDF ainda possuem comparacoes com status capitalizado antigo:
  - `Aprovado`
  - `Pendente`
  - `Rejeitado`
- O schema/model novo usa status em maiusculo. Isso deve ser padronizado ou suportado por propriedades auxiliares.
- `form_obra.html`, `inicio.html` e rotas de obra ainda referenciam campos legados que nao existem diretamente no model `Obra` atual:
  - `contrato`
  - `contratante` como campo editavel
  - `cnpj` como atributo persistente
- No model atual, `Obra.cnpj` e `Obra.contratante` sao propriedades derivadas; o campo persistente correto e `cnpj_obra`, e o vinculo de cliente deve usar `cliente_id`.
- A rota `gerar_obra` ainda referencia `EquipeObraAuxFuncoes`, mas esse model/tabela nao existe no schema atual.
- Algumas operacoes de exclusao ainda fazem delete fisico em filhos do RDO ou auxiliares. Deve ser revisto conforme regra de soft delete.
- O login atual registra apenas `usuarios.ultimo_login` e `ultimo_login_ip`; ainda falta gravar em `acesso_log` e criar/controlar `sessoes_usuario`.
- O upload de fotos do RDO ainda grava em `rdo_fotos`; a tabela generica `arquivos` ainda nao foi integrada ao fluxo.
- As notificacoes ainda nao estao integradas no cabecalho/base nem nas rotas.
- Os novos models `WorkflowDefinicao`, `WorkflowEtapa`, `Notificacao`, `Arquivo`, `SessaoUsuario`, `AcessoLog` e `RDOVersao` existem, mas ainda nao possuem rotas/telas integradas ao fluxo principal.
- O menu do `base.html` ainda e parcialmente controlado por papel/nome de role, nao por permissoes reais do RBAC.

### Recomendacao arquitetural para rotas

- O arquivo `app/routes/auth.py` esta grande demais e concentra responsabilidades que deveriam estar separadas.
- Hoje ele mistura:
  - autenticacao
  - setup inicial
  - dashboard
  - empresa/perfil
  - RDO
  - workflow/assinaturas
  - usuarios
  - obras
  - auxiliares
  - PDFs
  - validacao publica de documentos
- Da para continuar temporariamente assim, mas o risco de regressao aumenta a cada nova alteracao.
- A recomendacao e decompor aos poucos, primeiro movendo blocos sem alterar comportamento.
- Estrutura sugerida:
  - `app/routes/auth.py`
    - login
    - logout
    - setup
    - esqueci senha
    - redefinir senha
    - alteracao obrigatoria de senha
  - `app/routes/dashboard.py`
    - `/inicio`
    - KPIs
    - graficos do painel inicial
  - `app/routes/rdo.py`
    - criar RDO
    - editar RDO
    - visualizar RDO
    - listar RDO
    - excluir/desativar RDO
    - APIs auxiliares usadas pelo formulario de RDO
  - `app/routes/rdo_assinaturas.py`
    - salvar workflow de assinaturas
    - aprovar RDO
    - rejeitar RDO
    - regras de sequencia de aprovacao
  - `app/routes/usuarios.py`
    - lista de usuarios
    - criar usuario
    - editar usuario
    - visualizar usuario
    - ativar/desativar usuario
    - reset de senha
  - `app/routes/obras.py`
    - lista de obras
    - criar obra
    - editar obra
    - visualizar obra
    - ativar/desativar obra
    - frentes de trabalho
    - vinculos de equipe
  - `app/routes/auxiliares.py`
    - clima
    - equipamentos
    - tags de ocorrencia
    - funcoes/mao de obra
    - tipo de obra futuramente
  - `app/routes/documentos.py`
    - gerar PDF completo
    - gerar PDF compacto
    - validacao publica de documento
    - uploads/documentos futuros
  - `app/routes/perfil.py`
    - meu perfil
    - atualizar perfil
    - alterar minha senha
- Ordem recomendada de refatoracao:
  1. Criar os novos arquivos de rota e blueprints.
  2. Mover blocos por dominio, sem mudar regra de negocio.
  3. Registrar os novos blueprints em `app/__init__.py`.
  4. Preservar endpoints existentes sempre que possivel para nao quebrar `url_for` nos templates.
  5. Rodar a aplicacao e corrigir imports.
  6. Depois da separacao, padronizar RBAC, multiempresa, auditoria e soft delete.
- Primeiro alvo recomendado:
  - extrair o dominio de RDO para `app/routes/rdo.py`, pois e o maior bloco e o mais critico para o sistema.

## Falta fazer

### Banco de dados

- Executar o script SQL completo em um MySQL real para validar:
  - sintaxe final
  - ordem de criacao das tabelas
  - constraints e foreign keys
  - inserts de seed
  - triggers
- Corrigir possiveis inconsistencias apontadas pelo MySQL apos a primeira execucao real.
- Avaliar se a FK de `cad_listas.criado_por` e `cad_listas.modificado_por` deve permanecer no DDL, pois a tabela e criada antes de `usuarios` e hoje depende de `FOREIGN_KEY_CHECKS = 0`.
- Avaliar se o trigger `trg_rdo_numero_sequencial` deve respeitar `empresa_id` alem de `obra_id`.
- Padronizar acentuacao/encoding do arquivo SQL para evitar textos corrompidos em consoles Windows.

### Models e migracoes

- Rodar `scripts/diagnostics/import_check.py` em um Python funcional.
- Conferir se todos os models refletem 100% o DDL, incluindo:
  - constraints unicas
  - indices
  - nullability
  - defaults
  - nomes de enums
- Atualizar `app/__init__.py` para importar todos os modulos de models relevantes durante a inicializacao, garantindo que Alembic/Flask-Migrate enxergue todas as tabelas.
- Criar migrations Alembic reais a partir dos models, caso o projeto passe a usar migracoes em vez do script SQL direto.
- Remover ou ignorar arquivos `__pycache__` do versionamento, se estiverem sendo rastreados.

### Backend e regras de negocio

- Implementar middleware/funcoes de auditoria automatica usando `auditoria_log`.
- Implementar controle multiempresa obrigatorio nas queries:
  - `empresa_id = current_user.empresa_id`
- Implementar decorators/servicos de permissao, incluindo `@permission_required`.
- Implementar soft delete padronizado usando `ativo = FALSE`.
- Implementar bloqueio de edicao para RDO aprovado.
- Implementar versionamento automatico do RDO aprovado em `rdo_versoes`.
- Implementar workflow de aprovacao baseado em `workflow_definicoes` e `workflow_etapas`.
- Implementar criacao e leitura de `notificacoes`.
- Implementar controle real de sessoes em `sessoes_usuario` e `acesso_log`.
- Implementar upload/download de arquivos usando a tabela `arquivos`.
- Implementar transacoes com rollback em operacoes criticas.
- Implementar verificacao de alteracao real antes de salvar edicoes.

### Rotas e telas

- Criar/atualizar rotas CRUD para:
  - clientes
  - fornecedores
  - colaboradores
  - usuarios
  - obras
  - frentes de trabalho
  - auxiliares
  - workflows
  - notificacoes
  - arquivos/documentos
- Atualizar telas de RDO para respeitar:
  - status `RASCUNHO`, `PENDENTE`, `APROVADO`, `REJEITADO`, `CANCELADO`
  - bloqueio apos aprovacao
  - workflow configuravel
  - versionamento
- Criar dashboard dinamico por perfil:
  - administrador plataforma
  - administrador empresa
  - administrador obra
  - administrador frente
- Implementar menu dinamico conforme permissoes.
- Implementar notificacoes no cabecalho.
- Revisar todos os templates para garantir IDs HTML compativeis com banco/model.

### Exportacoes e BI

- Garantir exportacao PDF, XLSX, CSV e impressao em todas as listagens principais.
- Criar camada de exports reutilizavel.
- Preparar consultas/visoes para indicadores:
  - produtividade
  - SLA
  - lead time
  - historico operacional
  - aprovacoes pendentes

### Seguranca

- Confirmar hashing seguro de senhas.
- Revisar CSRF em todos os formularios.
- Implementar rate limit em login e rotas sensiveis.
- Reforcar protecao contra XSS em campos textuais.
- Implementar expiracao de sessao e logout remoto.
- Garantir controle de permissao por rota e por acao.

### Infraestrutura e qualidade

- Corrigir o ambiente Python local para permitir rodar scripts e testes.
- Validar Docker Compose com MySQL e app Flask.
- Rodar testes automatizados existentes.
- Criar novos testes para:
  - multiempresa
  - RBAC
  - workflow
  - RDO aprovado imutavel
  - versionamento
  - auditoria
  - uploads
- Atualizar README com setup, carga de banco e usuarios de seed.
