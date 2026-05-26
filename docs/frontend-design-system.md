# Frontend Design System (Admin)

Este projeto está evoluindo os templates Flask para um micro framework administrativo reutilizável (enterprise-ready).

## Objetivos

- Reduzir HTML repetido nos templates.
- Padronizar toolbar, tabela, empty state e actions.
- Preparar UI para permissões (RBAC/ACL) sem reescrever telas.
- Garantir boa experiência mobile para tabelas densas.

## Arquitetura (camadas)

1. **Tokens & Semantics (CSS)**
   - `app/static/css/enterprise_theme.css`
   - Define tokens em `:root` e classes semânticas `ds-*` (ex.: `ds-toolbar`, `ds-card`, `ds-empty-state`).

2. **Macros (Jinja)**
   - `app/templates/components/table/macros.html`
     - `wrapper(config=...)`: container padrão (card).
     - `toolbar(...)`: busca + botão de criar + área para ações extras.
     - `empty_state(...)`: empty state desacoplado (ícone/título/descrição).
     - `actions_dropdown(...)`: dropdown enterprise (permissions-ready).
   - `app/templates/components/macros.html`
     - `audit_info(...)`: bloco de auditoria reutilizável (nome/iniciais/data).

3. **List screens (templates)**
   - Padrão: definir um config por tela (ex.: `TABLE_OBRAS_CONFIG`) e montar a tela por macros.
   - DataTables: preferir `window.AdminTables.initWithSearch({ tableSelector, searchInputSelector, dataTableOptions })`.

## Convenções

### Config-driven tables

Cada list deve ter um dict `TABLE_*_CONFIG` contendo ao menos:

- `datatable_id`
- `title`
- `icon`
- `search_id` / `search_placeholder`
- `create_url` / `create_label` / `create_permission` (opcional)
- `mode` (ex.: `comfortable`, `dense`)

### Toolbar reutilizável

```jinja2
{% call ui_table.toolbar(
  search_id="obraSearch",
  create_url=url_for("auth.criar_obra"),
  create_label="Nova Obra",
  create_permission="obra.manage"
) %}
  {# filtros rápidos / export / ações secundárias #}
{% endcall %}
```

### Empty state desacoplado

```jinja2
{{ ui_table.empty_state(
  not opcoes,
  icon='fa-building',
  title='Nenhuma Obra encontrada',
  description='Clique em "Nova Obra" para começar.'
) }}
```

### Actions dropdown (permissions-ready)

O dropdown aceita `permission` e filtra automaticamente usando `session['permissions']`:

```jinja2
{{ ui_table.actions_dropdown(actions=[
  {'label': 'Visualizar', 'icon': 'fa-eye', 'url': url_for('auth.visualizar_obra', id=obra.id)},
  {'label': 'Editar', 'icon': 'fa-pen', 'url': url_for('auth.editar_obra', id=obra.id), 'permission': 'obra.manage'},
  {'divider': true},
  {'label': 'Inativar', 'icon': 'fa-ban', 'onclick': 'toggleObraStatus(' ~ obra.id ~ ')', 'permission': 'obra.manage'},
]) }}
```

### Mobile: labels em TD

Para tabelas com muitas colunas:

- `class="ds-mobile-labels"` na tabela
- `data-label="Nome da coluna"` em cada `td`

CSS: `app/static/css/enterprise_theme.css` (`td::before { content: attr(data-label) }`).

### Auditoria (`audit_info`)

Use para padronizar a exibição de:

- nome do usuário (ou `Sistema`)
- iniciais
- data (ex.: `Criado em`)

## Roadmap sugerido

- Padronizar dropdown de ações em todas as listas.
- Consolidar badge/status em macros por domínio.
- Evoluir filtros rápidos para um componente de filtros.
- Centralizar configs de tabelas em Python (ex.: `TABLE_OBRAS_CONFIG` no backend).
