# Plano de Refatoracao por Branches e Commits

Este plano foi criado com base no `docs/Contexto.md` atual do projeto. A ideia e evoluir o sistema sem uma refatoracao gigante de uma vez: primeiro separar responsabilidades, depois alinhar schema/models/rotas, depois adicionar regras corporativas como RBAC real, auditoria, workflow, notificacoes e arquivos.

## Padrao de Commits

Use Conventional Commits:

```text
tipo(escopo): descricao curta no imperativo
```

Tipos usados neste plano:

- `feat`: nova funcionalidade.
- `fix`: correcao de bug.
- `docs`: documentacao.
- `style`: formatacao sem mudanca de comportamento.
- `refactor`: reorganizacao sem nova funcionalidade.
- `test`: testes.
- `chore`: tarefas de build, ambiente, dependencias e manutencao.

Exemplos:

```text
refactor(routes): extraia rotas de rdo do auth
fix(rdo): normalize status em maiusculo
feat(audit): registre log de acesso no login
test(rbac): cubra permissao por rota
```

## Regras de Execucao

- Trabalhar uma branch por tema.
- Evitar misturar refatoracao estrutural com mudanca de regra de negocio no mesmo commit.
- Preservar endpoints existentes sempre que possivel para nao quebrar `url_for`.
- Rodar o app e testes ao final de cada branch.
- Fazer commits pequenos o bastante para reverter sem sofrimento.
- Atualizar o `docs/Contexto.md` quando uma branch fechar uma etapa importante.

## Branch 1 - Baseline e Ambiente

Branch:

```text
chore/baseline-validacao-ambiente
```

Objetivo:

Criar uma base confiavel antes de mexer na arquitetura. Resolver importacao de models, ambiente Python e validacoes minimas.

Commits sugeridos:

```text
docs(context): registre sql validado no mysql
chore(env): corrija execucao do python local
chore(models): importe todos os models na inicializacao
test(diagnostics): valide importacao da aplicacao
chore(git): remova pycache do versionamento
```

Checklist:

- Confirmar que `scripts/diagnostics/import_check.py` roda.
- Ajustar `app/__init__.py` para importar todos os modulos de models relevantes.
- Garantir que Flask-Migrate/Alembic enxerga os novos models.
- Remover `__pycache__` rastreados, se estiverem no Git.
- Atualizar `.gitignore`, se necessario.

## Branch 2 - Separacao Inicial de Rotas

Branch:

```text
refactor/split-auth-routes
```

Objetivo:

Dividir `app/routes/auth.py` sem mudar comportamento. Esta branch deve ser o mais mecanica possivel.

Status em 2026-05-11:

- Separacao mecanica aplicada.
- `app/routes/auth.py` ficou responsavel por autenticacao, setup, recuperacao de senha e paginas institucionais.
- Foi criado `app/routes/auth_common.py` para concentrar blueprint, imports, constantes, decorators e helpers compartilhados.
- Foram criados modulos por dominio mantendo o mesmo `auth_bp`, para preservar endpoints como `auth.lista_rdo`, `auth.criar_rdo` e `auth.inicio`.
- A validacao Python ainda depende de corrigir o ambiente local, pois o executavel atual aponta para Microsoft Store e nao inicia.

Arquivos sugeridos:

- `app/routes/auth.py`
- `app/routes/dashboard.py`
- `app/routes/rdo.py`
- `app/routes/rdo_assinaturas.py`
- `app/routes/usuarios.py`
- `app/routes/obras.py`
- `app/routes/auxiliares.py`
- `app/routes/documentos.py`
- `app/routes/perfil.py`

Commits sugeridos:

```text
refactor(routes): crie blueprints por dominio
refactor(auth): mantenha apenas autenticacao no auth
refactor(dashboard): mova inicio para dashboard
refactor(rdo): mova rotas principais de rdo
refactor(rdo): mova apis auxiliares do formulario
refactor(assinaturas): mova fluxo de aprovacao
refactor(usuarios): mova rotas de usuarios
refactor(obras): mova rotas de obras
refactor(auxiliares): mova cadastros auxiliares
refactor(documentos): mova pdf e validacao publica
refactor(perfil): mova rotas de perfil
chore(app): registre novos blueprints
```

Checklist:

- Nenhuma regra de negocio nova nesta branch.
- Manter nomes de endpoint ou atualizar todos os `url_for` afetados.
- Confirmar que menus e botoes ainda navegam.
- Confirmar que login, dashboard, lista RDO e formulario RDO ainda abrem.

## Branch 3 - Compatibilidade com Schema Novo

Branch:

```text
fix/schema-route-compat
```

Objetivo:

Alinhar rotas/templates ao SQL e models atuais.

Commits sugeridos:

```text
fix(rdo): normalize status em maiusculo
fix(templates): ajuste comparacoes de status do rdo
fix(obras): troque campos legados por cliente_id
fix(obras): use cnpj_obra como campo persistente
fix(obras): remova dependencia de EquipeObraAuxFuncoes
fix(rdo): alinhe aliases de aprovacao no template
fix(pdf): atualize status e campos de obra no modelo
```

Checklist:

- Status validos no RDO:
  - `RASCUNHO`
  - `PENDENTE`
  - `APROVADO`
  - `REJEITADO`
  - `CANCELADO`
- Remover dependencia direta de status antigos:
  - `Aprovado`
  - `Pendente`
  - `Rejeitado`
- Ajustar obra:
  - usar `cliente_id`
  - usar `cnpj_obra`
  - tratar `contratante` como propriedade derivada do cliente
- Substituir ou recriar corretamente a logica de equipe que hoje referencia `EquipeObraAuxFuncoes`.

## Branch 4 - Multiempresa e RBAC Real

Branch:

```text
feat/security-rbac-multitenant
```

Objetivo:

Padronizar acesso por `empresa_id` e permissao real por rota.

Commits sugeridos:

```text
refactor(security): centralize usuario atual e empresa
feat(rbac): padronize decorator permission_required
fix(rdo): filtre lista por empresa atual
fix(auxiliares): inclua auxiliares globais e da empresa
fix(admin): restrinja dados por empresa quando aplicavel
refactor(menu): controle navegacao por permissoes
test(security): cubra isolamento multiempresa
test(rbac): cubra permissoes principais
```

Checklist:

- Toda query operacional deve filtrar `empresa_id`.
- Auxiliares devem consultar:
  - `empresa_id = current_user.empresa_id`
  - ou `empresa_id IS NULL` para registros globais.
- Substituir gradualmente `role_required` por `permission_required`.
- Menu principal deve seguir permissao, nao apenas nome do papel.

## Branch 5 - Soft Delete e Transacoes

Branch:

```text
refactor/persistence-soft-delete
```

Objetivo:

Padronizar exclusoes logicas e transacoes.

Commits sugeridos:

```text
refactor(crud): centralize soft delete
fix(rdo): troque exclusao fisica por ativo false
fix(auxiliares): preserve registros em exclusao
fix(obras): desative obras sem remover historico
refactor(db): use transacoes em operacoes criticas
test(crud): cubra soft delete operacional
```

Checklist:

- Nenhum registro operacional deve ser removido fisicamente.
- Excecoes aceitaveis devem ser documentadas.
- Operacoes com multiplas tabelas devem ter rollback claro.

## Branch 6 - Auditoria e Sessoes

Branch:

```text
feat/auditoria-sessoes
```

Objetivo:

Ligar `auditoria_log`, `acesso_log` e `sessoes_usuario` ao fluxo real.

Commits sugeridos:

```text
feat(audit): crie servico de auditoria
feat(auth): registre login no acesso_log
feat(auth): controle sessoes de usuario
feat(auth): implemente logout remoto
feat(audit): registre alteracoes criticas
test(audit): cubra logs de operacoes criticas
```

Checklist:

- Login deve registrar:
  - usuario
  - empresa
  - IP
  - user agent
  - sucesso/falha
- Sessao ativa deve ser rastreavel.
- Operacoes criticas devem registrar antes/depois.

## Branch 7 - Workflow Corporativo

Branch:

```text
feat/workflow-aprovacao
```

Objetivo:

Substituir fluxo ad hoc por `workflow_definicoes` e `workflow_etapas`.

Commits sugeridos:

```text
feat(workflow): crie servico de resolucao de fluxo
feat(workflow): gere aprovacoes por etapas
feat(workflow): suporte aprovacao sequencial
feat(workflow): suporte aprovacao paralela configuravel
fix(rdo): bloqueie edicao apos aprovacao final
feat(rdo): versione rdo aprovado
test(workflow): cubra aprovacao e rejeicao
```

Checklist:

- Workflow por empresa.
- Workflow por obra.
- SLA por etapa.
- Rejeicao deve seguir configuracao.
- Aprovacao final deve bloquear RDO e criar `rdo_versoes`.

## Branch 8 - Notificacoes

Branch:

```text
feat/notificacoes
```

Objetivo:

Integrar `notificacoes` no cabecalho, dashboard e workflow.

Commits sugeridos:

```text
feat(notificacoes): crie servico de notificacao
feat(notificacoes): liste pendencias no cabecalho
feat(rdo): notifique novo rdo
feat(workflow): notifique aprovacao pendente
feat(workflow): notifique rejeicao
test(notificacoes): cubra leitura e criacao
```

Checklist:

- Mostrar contador no header.
- Permitir marcar como lida.
- Gerar notificacoes em eventos de RDO.

## Branch 9 - Arquivos e Uploads

Branch:

```text
feat/arquivos-documentos
```

Objetivo:

Usar a tabela `arquivos` para upload/download rastreavel.

Commits sugeridos:

```text
feat(arquivos): crie servico de armazenamento
feat(arquivos): registre uploads na tabela arquivos
refactor(rdo): integre fotos ao catalogo de arquivos
feat(documentos): cadastre contratos e anexos da obra
feat(documentos): implemente download seguro
test(arquivos): cubra upload e rastreabilidade
```

Checklist:

- Suportar provider `LOCAL` primeiro.
- Deixar extensao para S3/Azure/MinIO.
- Registrar hash, tamanho, mime type e usuario.

## Branch 10 - Exportacoes e BI

Branch:

```text
feat/exports-bi
```

Objetivo:

Padronizar exportacoes e preparar indicadores.

Commits sugeridos:

```text
feat(exports): crie camada comum de exportacao
feat(rdo): exporte lista em csv/xlsx/pdf com visualizacao atual
feat(obras): exporte cadastros em csv/xlsx/pdf com visualizacao atual
feat(bi): adicione indicadores de produtividade, SLA e lead time
test(exports): cubra exportacoes principais
docs(context): registre marco exports-bi e BI
```

Checklist:

- Exportar visualizacao atual mantendo filtros e pagina atual.
- Exportar conjunto completo mantendo filtros mas todas as colunas.
- Suportar PDF, XLSX e CSV para listagens principais.
- Indicadores:
  - produtividade
  - SLA
  - lead time
  - historico operacional

Status: concluído em 2026-05-20

Resultado entregue:

- Camada comum de exportação centralizada.
- Exportação de `list_rdo` e `list_obras` com suporte a visualização atual e conjunto completo.
- Exportação em `CSV`, `XLSX` e `PDF`.
- Indicadores operacionais básicos implementados.
- Documentação do marco registrada em `docs/Contexto.md`.

## Branch 11 - Testes e Hardening

Branch:

```text
test/hardening-suite
```

Objetivo:

Consolidar seguranca e estabilidade.

Commits sugeridos:

```text
test(auth): cubra login e recuperacao de senha
test(rdo): cubra ciclo completo de rdo
test(security): cubra isolamento por empresa
test(workflow): cubra bloqueio apos aprovacao
test(files): cubra upload e validacao
fix(security): corrija falhas encontradas nos testes
docs(readme): documente setup e seeds
```

Checklist:

- Testes para multiempresa.
- Testes para RBAC.
- Testes para workflow.
- Testes para RDO aprovado imutavel.
- Testes para auditoria.
- Testes para upload.

# Branch 12 - Definições Corporativas e Configuração por Empresa

Branch:

```text
feat/configuracoes-empresa-rbac
```

## Objetivo

Criar uma camada central de definições por empresa, permitindo configurações customizadas, herança por obra e integração com RBAC.

## Escopo

### Definições da Empresa

Criar tela central de configurações corporativas:

- Nome fantasia
- Logo
- Timezone
- Cores do sistema
- Configurações do workflow
- Configurações do RDO
- Configurações de notificações
- Configurações operacionais
- Configurações gerais do sistema

---

### Definições por Obra

Permitir herança de configurações:

```text
Empresa
   ↓
Obra
```

Exemplo:

```text
Empresa:
- Workflow padrão: 3 aprovações

Obra A:
- Workflow customizado: 2 aprovações
```

Caso não exista configuração própria da obra:

```text
Obra → Empresa → Sistema
```

---

### RBAC

Permitir visualização e gerenciamento de:

- Papéis globais
- Papéis personalizados da empresa

Exemplo:

```text
Sistema:
- Admin
- Operador
- Leitor

Empresa:
- Gestor Obra
- Fiscal Cliente
- Supervisor Produção
```

---

### Estrutura sugerida

Tabelas:

```text
empresa_config
obra_config
papel
papel_permissao
```

---

## Commits sugeridos

```text
feat(config): crie tabela empresa_config
feat(config): implemente configuracoes por obra
feat(rbac): exiba papeis globais e personalizados
feat(ui): implemente tela de definicoes corporativas
fix(config): aplique heranca empresa-obra
test(config): cubra configuracoes por empresa
```

---

## Checklist

- [ ] Criar configurações por empresa
- [ ] Criar configurações por obra
- [ ] Aplicar herança Empresa → Obra
- [ ] Exibir papéis globais
- [ ] Exibir papéis personalizados
- [ ] Aplicar configurações em runtime
- [ ] Adicionar testes


---

# Branch 13 - Gestão de Colaboradores e Mão de Obra

Branch:

```text
feat/colaboradores-frente-rdo
```

## Objetivo

Transformar colaboradores em entidade operacional integrada ao fluxo do RDO.

## Escopo

### Cadastro de colaboradores

Campos sugeridos:

```text
nome
cpf
matricula
funcao
empresa_id
ativo
eh_usuario
usuario_id
```

---

### Integração com usuário

Adicionar opção no formulário:

```text
[ ] Criar acesso ao sistema
```

Regras:

Se marcado:

```text
Criar Usuario
Criar UsuarioPapel
Relacionar Colaborador.usuario_id
```

Se desmarcado:

```text
Criar apenas colaborador operacional
```

---

### Integração com Frente de Trabalho

Permitir vincular colaboradores:

Exemplo:

```text
Frente Trabalho A

- João
- Pedro
- Carlos
```

Tabela sugerida:

```text
frente_colaborador
```

---

### Integração automática com RDO

Fluxo:

```text
Frente Trabalho
        ↓
Colaboradores vinculados
        ↓
Criar RDO
        ↓
Mão de obra preenchida automaticamente
```

---

## Commits sugeridos

```text
feat(colaborador): implemente cadastro operacional
feat(usuario): permita criar usuario a partir de colaborador
feat(frente): vincule colaboradores a frente
feat(rdo): carregue mao de obra automaticamente
test(colaborador): cubra integracao colaborador-rdo
```

---

## Checklist

- [ ] Criar cadastro operacional
- [ ] Permitir vínculo opcional com usuário
- [ ] Vincular colaboradores às frentes
- [ ] Carregar mão de obra automaticamente no RDO
- [ ] Adicionar testes


---

# Branch 14 - Revisão de Templates e Design System

Branch:

```text
refactor/templates-design-system
```

## Objetivo

Padronizar templates, remover inconsistências visuais, eliminar código legado e criar componentes reutilizáveis.

## Escopo

### Layout e UX

Padronizar:

- Espaçamentos
- Tipografia
- Tabelas
- Botões
- Formulários
- Badges
- Cards
- Responsividade
- Feedback visual

---

### Limpeza

Remover:

- HTML comentado
- Código morto
- Componentes duplicados
- CSS repetido
- Scripts inline desnecessários

---

### Componentização

Estrutura sugerida:

```text
templates/components/

badge.html
table.html
card.html
modal.html
pagination.html
notification.html
```

---

### Performance

Melhorias:

- Extrair JavaScript inline
- Reduzir CSS repetido
- Centralizar componentes reutilizáveis
- Reduzir lógica dentro dos templates

---

## Commits sugeridos

```text
refactor(ui): padronize componentes visuais
refactor(template): remova codigo legado
refactor(layout): normalize formularios e tabelas
refactor(js): extraia scripts inline
style(ui): ajuste responsividade
```

---

## Checklist

- [ ] Criar componentes reutilizáveis
- [ ] Padronizar layout
- [ ] Melhorar responsividade
- [ ] Remover código morto
- [ ] Extrair scripts inline
- [ ] Reduzir lógica nos templates
- [ ] Adicionar testes


## Marcos de Entrega

### Marco 1 - Base saudável

**Status:** concluído em 2026-05-12

#### Verificação (2026-05-12)

- Branch 1: `app/__init__.py` importa os módulos de models na inicialização e existe `scripts/diagnostics/import_check.py`.
- Branch 2: separação de rotas aplicada com `app/routes/auth_common.py` e módulos por domínio registrados no mesmo `auth_bp`.
- Branch 3: compatibilidade de schema aplicada:
  - status em maiúsculo
  - `cliente_id`
  - `cnpj_obra`
  - remoção de dependência do modelo legado de equipe
  - correções de templates e aliases para manter navegação

#### Branches

- `chore/baseline-validacao-ambiente`
- `refactor/split-auth-routes`
- `fix/schema-route-compat`

#### Resultado esperado

- App inicia
- Rotas separadas
- Templates continuam navegáveis
- Schema novo integrado às rotas principais

---

### Marco 2 - Segurança, RBAC e regras corporativas

**Status:** concluído em 2026-05-14

#### Verificação (2026-05-14)

##### Multiempresa e RBAC

- Aplicado isolamento por `empresa_id`
- Implementado RBAC baseado em permissões
- Menu desacoplado de papéis fixos

##### Soft Delete e transações

Endpoint:

```text
POST /assinar-rdo/<int:rdo_id>/salvar-workflow
```

Arquivo:

```text
app/routes/rdo_assinaturas.py
```

Alterações:

- Exclusão física substituída por Soft Delete:

```python
ass.soft_delete(...)
```

- Preservação do histórico:

```text
ativo=False
```

- Operações agrupadas em transação:

```python
with db.session.begin()
```

##### Auditoria

Implementado:

```text
AuditoriaService
```

Eventos auditados:

- UPDATE (`gerar_rdo`)
- SOFT_DELETE (`excluir_rdo`)

Centralização:

```python
registrar_auditoria_entidade(...)
```

##### Navegação por permissões (RBAC)

Arquivo:

```text
app/templates/base.html
```

Substituído:

```python
session.user_role
```

por:

```python
session["permissions"]
```

Permissões aplicadas:

- `obra.manage`
- `usuario.manage`
- `mao_obra.view`
- `equipamento.view`
- `clima.view`
- `tag_ocorrencia.view`

##### Testes

Validação executada:

```bash
python -m pytest -q
```

Resultado:

```text
4 passed, 1 warning
```

Warning existente:

```text
test_login.py::test_login
```

#### Branches

- `feat/security-rbac-multitenant`
- `refactor/persistence-soft-delete`
- `feat/auditoria-sessoes`

#### Resultado esperado

- Multiempresa consistente
- RBAC real aplicado
- Auditoria operacional
- Sessões rastreáveis
- Rollback seguro

---

### Marco 3 - RDO Enterprise e arquivos rastreáveis

**Status:** concluído em 2026-05-20

#### Verificação (2026-05-20)

##### Workflow

Implementado:

- Workflow configurável
- Aprovação sequencial
- Aprovação paralela
- Versionamento de RDO
- Imutabilidade após aprovação

---

##### Notificações

Serviço:

```text
app/services/notificacao_service.py
```

Métodos:

```python
NotificacaoService.criar_notificacao()
NotificacaoService.listar_nao_lidas()
NotificacaoService.marcar_como_lida()
```

Endpoint:

```text
POST /notificacoes/<int:id>/lida
```

Recursos:

- autenticação obrigatória
- auditoria
- atualização automática de contador

Eventos:

- aprovação pendente
- aprovação concluída
- rejeição

Arquivos:

```text
app/routes/rdo.py
app/routes/rdo_assinaturas.py
```

---

##### Arquivos rastreáveis

Serviço:

```text
app/services/arquivo_service.py
```

Implementações:

- `hash_arquivo` (SHA-256)
- `tamanho_bytes`
- `mime_type`

Endpoints:

```text
POST /arquivos/upload
GET /arquivos/<int:arquivo_id>/download
```

Recursos:

- scoping por empresa
- provider `LOCAL`
- download seguro
- persistência em catálogo central

Integração:

```python
ArquivoService.save_local_file(...)
```

Testes:

```text
tests/test_arquivos.py
```

Cobertura:

- persistência de metadados
- download seguro
- rastreabilidade

#### Branches

- `feat/workflow-aprovacao`
- `feat/notificacoes`
- `feat/arquivos-documentos`

#### Resultado esperado

- Workflow configurável
- RDO imutável após aprovação
- Versionamento automático
- Notificações operacionais
- Upload rastreável
- Download seguro
- Catálogo centralizado de arquivos

---

### Marco 4 - Operação, qualidade e hardening

**Status:** concluído em 2026-05-21

#### Verificação (2026-05-21)

##### Exportações e indicadores

Implementado:

- camada comum de exportação
- exportação CSV
- exportação XLSX
- exportação PDF
- exportação da visualização atual
- exportação completa mantendo filtros
- indicadores operacionais iniciais

Indicadores:

- produtividade
- SLA
- lead time
- histórico operacional

---

##### Hardening Suite

Commit:

```text
cb69a1e
```

Descrição:

```text
feat: hardening suite (auditoria/notificações/rbac/multiempresa)
```

Implementado:

- fortalecimento da auditoria
- reforço das notificações
- ajustes de sessão e usuário
- melhorias de segurança
- melhorias em RBAC
- expansão da cobertura de testes
- testes de fluxo completo
- validação de imutabilidade
- inclusão de artefatos:

```text
uploads/testes/
```

- reorganização dos testes existentes

#### Branches

- `feat/exports-bi`
- `test/hardening-suite`

#### Resultado esperado

- Exportações principais
- Indicadores operacionais
- Cobertura de segurança
- Cobertura de fluxos críticos
- README atualizado

---

## Novo marco (Commit por features)

### 2026-05-21

**Commit**

```text
cb69a1e
```

**Descrição**

```text
feat: hardening suite (auditoria/notificações/rbac/multiempresa)
```

**Resumo**

- Fortalecimento de auditoria
- Ajustes de sessão e usuário
- Melhorias de segurança
- Expansão de testes automatizados
- Inclusão de artefatos de validação
- Reorganização do suite de testes

## Observacoes Importantes

- O script SQL ja foi executado no MySQL com sucesso, segundo validacao manual.
- Ainda falta validar a aplicacao Flask com Python funcional.
- O maior risco atual esta na diferenca entre rotas/templates legados e schema novo.
- A primeira grande vitoria tecnica deve ser separar `auth.py`; depois disso, cada dominio fica muito mais facil de corrigir.
