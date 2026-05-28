# Branch 14 — refactor/templates-design-system

## Objetivo
Padronizar templates (layout/UX), remover inconsistências e legado, criar componentes reutilizáveis e reduzir acoplamento de HTML/CSS/JS.

## Critérios de Aceitação (Definition of Done)
- Todas as rotas existentes continuam renderizando com status HTTP 200.
- Componentes criados em `app/templates/components/` são efetivamente usados em telas (não ficam órfãos).
- Remoção/limpeza:
  - remover HTML comentado e código morto (sem alterar comportamento)
  - remover `<style>` inline e scripts inline do `app/templates/base.html` e movê-los para `app/static/css/*` e `app/static/js/*`.
- Responsividade consistente (cards/tabelas/form/grid) usando o mesmo padrão de classes.
- Testes:
  - smoke tests de renderização dos componentes + smoke de pelo menos 3 rotas principais.

## Dependências & Observações do projeto (RDO / Flask / Tailwind)
- O projeto usa Tailwind via CDN no `base.html` e CSS locais em `app/static/css/*`.
- Existem vários templates com `<script>` inline e bibliotecas externas (ex.: DataTables, Select2, SignaturePad, PDF.js).
- Para extração de JS/CSS, respeitar integrações:
  - wrapper/handlers do projeto podem ir para `app/static/js/*`
  - includes de bibliotecas externas (CDN) podem continuar onde já estão (ou migrar depois, fase seguinte).

## Fase A — Inventário e mapeamento (Commit 1)
### A1) Encontrar repetição visual
- Identificar padrões repetidos de:
  - cards (seções com título/descrição/ações)
  - tabelas (thead/tbody/empty state/toolbar)
  - badges/status
  - flash messages
  - modais/paginação

### A2) Mapear scripts inline
- Levantar todos os `<script>` inline em `app/templates/*.html`.
- Prioridade imediata (alta):
  - `app/templates/base.html`
    - `toggleMobileMenu()`
    - `toggleMobileSubmenu()`
    - lógica de toasts (`.toast-message`)
    - injeção de `csrf_token` em forms
    - `markNotificacaoLidaFromElement()`
- Prioridade alta (média/risco):
  - páginas de listagem com DataTables:
    - `list_rdo.html`, `list_obras.html`, `list_mao_obra.html`, `list_climas.html`, `list_equipamentos.html`, `list_tags_ocorrencias.html`, `list_usuarios.html`
  - páginas de forms com JS próprio:
    - `form_mao_obra.html`, `form_equipamento.html`, `form_clima.html`, `form_tags_ocorrencias.html`, `form_usuario.html`, `form_obra.html`, `form_rdo.html`, `empresa.html`, `admin/empresa_form.html`, `admin/fornecedor_form.html`
  - integrações externas:
    - `signature_pad` em `form_rdo.html`
    - `select2` em `form_rdo.html` / `admin/fornecedor_form.html`
    - `pdf.js` em `public_validacao.html`

### A3) Listar templates candidatos (componente alvo)
- Categorizar telas por prioridade:
  1) `form_*.html` e telas de edição/cadastro: **alvo card + botões + flash**
  2) `list_*.html`: **alvo table + toolbar**
  3) templates institucionais: **alvo cards simples** (se houver repetição)
  4) `admin/*`: aplicar padronização apenas quando houver duplicação clara

**Saída esperada da Fase A (artefatos):**
- Atualizar este backlog com:
  - lista de templates candidatos
  - lista de scripts inline por responsabilidade
  - lista de componentes candidatos (com parâmetros e slots)
  - riscos por integração (DataTables/Select2/SignaturePad/PDF.js)


## Fase B — Criar componentes reutilizáveis (Commit 2)
Criar estrutura:
```text
app/templates/components/
  badge.html
  button.html
  table.html
  card.html
  modal.html
  pagination.html
  notification.html
  macros.html
```

### B1) `badge.html`
- Parâmetros: `text`, `variant` (mapeado em classes Tailwind)
- Sem lógica de negócio.

### B2) `button.html`
- Parâmetros: `label`, `variant`, `icon`, `href`, `type`, `disabled`, `size`
- Sem lógica de negócio.

### B3) `card.html`
- Slots: `header`, `body`, `actions` (ou parâmetros equivalentes)
- Padroniza `rounded-2xl`, `shadow-sm`, `border`, `p-6`.

### B4) `table.html`
- Parâmetros: `headers`, `rows`, `empty_text`, `actions` (opcional)
- Inclui `overflow-x-auto`, hover em linhas.

### B5) `modal.html`
- Parâmetros: `id`, `title`, `body`, `footer`

### B6) `pagination.html`
- Parâmetros: `page`, `total_pages`, `url_for_page` (ou slots)

### B7) `notification.html`
- Parâmetros: `notifications`, `unread_count`, `mark_url` (ou usar variáveis passadas pelo contexto)
- Mantém compatibilidade com o dropdown atual do `base.html`.

### B8) `macros.html`
- Macros para evitar muitos `{% include %}` em repetição:
  - `badge()`
  - `button()`
  - `pagination()` (se aplicável)

## Fase C — Padronizar layout usando componentes (Commits 3–5)
### C1) Formulários
- Refatorar `form_*.html` para usar `components/card.html` e `components/button.html`.
- Padronizar erros/feedback (quando existir padrão nos templates atuais).

### C2) Listagens
- Refatorar `list_*.html` para usar `components/table.html`.
- Unificar container responsivo e empty state.

### C3) Admin
- Aplicar o mesmo padrão aos templates `admin/*` onde houver duplicação significativa.

## Fase D — Extrair CSS inline do `base.html` (Commit 6)
- Remover `<style>` inline do `app/templates/base.html`.
- Criar `app/static/css/design-system.css` (ou expandir `components.css`).
- Incluir no `base.html`:
  - `design-system.css`

## Fase E — Extrair JS inline do `base.html` (Commit 7)
- Remover scripts inline do `app/templates/base.html` e criar:
  - `app/static/js/ui.js` (menu mobile, dropdown, toast)
  - `app/static/js/csrf.js` (injeção de csrf_token, se realmente necessário)
  - `app/static/js/notifications.js` (markNotificacaoLida)
- Referenciar com `<script src=... defer></script>`.

## Fase F — Limpeza e remoção de legado (Commit 8)
- Remover:
  - HTML comentado
  - código morto (não referenciado)
  - CSS repetido (substituir por tokens/utility/component)
  - scripts inline desnecessários
- Garantir que integrações (DataTables/Select2/SignaturePad/PDF.js) continuam funcionando.

## Fase G — Testes (Commit final)
- Criar `tests/templates/test_component_render.py` com smoke tests por template de componente.
- Criar smoke tests de 3 rotas essenciais para garantir que includes/componentização não quebram render.

## Plano de commits sugerido (alinhado ao escopo)
1. `refactor(template): inventory and design system backlog`
2. `refactor(ui): create templates components (badge/table/card/modal/pagination/notification + button)`
3. `refactor(layout): standardize forms and tables with components`
4. `refactor(template): apply partials and simplify base/layout`
5. `style(ui): move base.html inline CSS to design-system.css`
6. `refactor(js): move base.html inline scripts to static js modules`
7. `refactor(template): remove legacy commented/dead code and duplication`
8. `test(template): add component render smoke tests`

