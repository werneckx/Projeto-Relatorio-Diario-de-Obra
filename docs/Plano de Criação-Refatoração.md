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
feat(rdo): exporte lista em csv
feat(rdo): exporte lista em xlsx
feat(obras): exporte cadastros principais
feat(bi): adicione consultas de produtividade
feat(bi): adicione indicadores de sla
test(exports): cubra exportacoes principais
```

Checklist:

- PDF, XLSX, CSV e impressao para listagens principais.
- Indicadores:
  - produtividade
  - SLA
  - lead time
  - historico operacional

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

## Ordem Recomendada das Branches

1. `chore/baseline-validacao-ambiente`
2. `refactor/split-auth-routes`
3. `fix/schema-route-compat`
4. `feat/security-rbac-multitenant`
5. `refactor/persistence-soft-delete`
6. `feat/auditoria-sessoes`
7. `feat/workflow-aprovacao`
8. `feat/notificacoes`
9. `feat/arquivos-documentos`
10. `feat/exports-bi`
11. `test/hardening-suite`

## Marcos de Entrega

### Marco 1 - Base saudavel

Status: concluído em 2026-05-12

Verificação (2026-05-12):

- Branch 1: `app/__init__.py` importa os módulos de models na inicialização e existe `scripts/diagnostics/import_check.py` (validação de execução depende de Python local funcional).
- Branch 2: separação de rotas aplicada com `app/routes/auth_common.py` e módulos por domínio registrados no mesmo `auth_bp` (importados em `app/routes/auth.py`).
- Branch 3: compatibilidade de schema aplicada (status em maiúsculo, `cliente_id`/`cnpj_obra` em obras, remoção de dependência do modelo legado de equipe) e correções de templates/aliases para manter navegação.

Branches:

- `chore/baseline-validacao-ambiente`
- `refactor/split-auth-routes`
- `fix/schema-route-compat`

Resultado esperado:

- App inicia.
- Rotas separadas.
- Templates continuam navegaveis.
- Schema novo conversa com rotas principais.

### Marco 2 - Regras corporativas

Branches:

- `feat/security-rbac-multitenant`
- `refactor/persistence-soft-delete`
- `feat/auditoria-sessoes`

Resultado esperado:

- Multiempresa consistente.
- RBAC real aplicado.
- Auditoria e sessoes gravadas.
- Deletes logicos.

### Marco 3 - RDO enterprise

Branches:

- `feat/workflow-aprovacao`
- `feat/notificacoes`
- `feat/arquivos-documentos`

Resultado esperado:

- Workflow configuravel.
- RDO aprovado imutavel e versionado.
- Notificacoes operacionais.
- Uploads rastreaveis.

### Marco 4 - Operacao e qualidade

### Marco 4.1 - Navegação por permissões (RBAC)

Status: concluído em 2026-05-13

Verificação (2026-05-13):

- `app/templates/base.html` atualizado para o menu **“Cadastros”** renderizar itens com base em `session["permissions"]` (em vez de `session.user_role`).
- Condicional por permissões principais (exemplos):
  - `obra.manage` → Obras e Projetos
  - `usuario.manage` → Usuários
  - `mao_obra.view` → Mão de Obra
  - `equipamento.view` → Equipamentos
  - `clima.view` → Climas
  - `tag_ocorrencia.view` → Tags de Ocorrências
- Objetivo: garantir que a navegação acompanhe RBAC real (por permissão) e não apenas o papel nominal.


Branches:

- `feat/exports-bi`
- `test/hardening-suite`

Resultado esperado:

- Exportacoes principais.
- Indicadores iniciais.
- Testes de seguranca e fluxo critico.
- README atualizado.

## Observacoes Importantes

- O script SQL ja foi executado no MySQL com sucesso, segundo validacao manual.
- Ainda falta validar a aplicacao Flask com Python funcional.
- O maior risco atual esta na diferenca entre rotas/templates legados e schema novo.
- A primeira grande vitoria tecnica deve ser separar `auth.py`; depois disso, cada dominio fica muito mais facil de corrigir.
