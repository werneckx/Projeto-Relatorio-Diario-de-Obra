## Branch: feature/database-seeds-workflow

### Banco de Dados
- [x] Revisar a arquitetura atual do banco de dados para suportar workflows configuráveis.
- [x] Validar relacionamentos entre Empresa, Obra, Workflow, Etapas e Responsáveis.
- [x] Verificar se as tabelas existentes atendem aos requisitos funcionais.
- [x] Identificar estruturas faltantes para configurações dinâmicas.

### Seeds Completos para utilizar o sistema. Verifique quais funcionalidades eu tenho no meu sistema e deixe completo. Script Banco de Dados.
- [x] Criar seeds de permissões.
- [x] Criar seeds de papéis.
- [x] Criar seeds de definições.
- [x] Criar seeds de configurações padrão.
- [x] Criar seeds de workflows.
- [x] Criar seeds de etapas de workflow.
- [x] Criar seeds de exemplos para Empresa e Obra.

### Backend
- [x] Verificar se já existe suporte para:
  - Aprovação.
  - Reprovação.
  - Assinatura.
  - Encerramento.
  - Reabertura.
- [x] Identificar lacunas arquiteturais existentes.

---

## Branch: feature/workflow-configuracoes

### Workflow
- [x] Implementar seleção de workflow por Empresa.
- [x] Implementar seleção de workflow por Obra.
- [x] Definir regra de herança Empresa → Obra.
- [x] Implementar fallback para workflow padrão da Empresa.

### Responsáveis
- [x] Definir modelo de responsáveis por papel.
- [x] Definir modelo de responsáveis por etapa.
- [x] Permitir configuração de responsáveis na Empresa.
- [x] Permitir sobrescrita de responsáveis na Obra.
- [x] Garantir que novos workflows utilizem as configurações atualizadas.

### Execução
- [x] Validar disparo automático do workflow na criação do RDO.
- [x] Garantir identificação correta dos aprovadores.
- [x] Garantir persistência da execução do workflow.

---

## Branch: feature/permissoes-papeis

### Papéis
- [ ] Revisar estrutura atual de papéis.
- [ ] Validar compatibilidade com workflows configuráveis.
- [ ] Permitir customização de permissões por papel.

### Permissões
- [ ] Revisar permissões existentes.
- [ ] Criar permissões ausentes.
- [ ] Remover permissões obsoletas.
- [ ] Garantir associação correta entre papel e permissão.

### Workflow
- [ ] Garantir atribuição automática de permissões de assinatura.
- [ ] Garantir atribuição automática de permissões de aprovação.
- [ ] Validar permissões durante a execução do workflow.

### Testes
- [ ] Validar comportamento para todos os papéis.
- [ ] Validar cenários de aprovação.
- [ ] Validar cenários de assinatura.

---

## Branch: feature/empresa-configuracoes

### Template Empresa
- [ ] Refatorar tela de Empresa.
- [x] Permitir seleção de workflow padrão.
- [ ] Permitir configuração de definições.
- [ ] Permitir configuração de papéis.
- [ ] Permitir configuração de permissões.
- [ ] Permitir configuração de responsáveis.

### Configurações
- [ ] Permitir ativação/desativação de funcionalidades.
- [ ] Permitir configuração de comportamento padrão dos RDOs.
- [ ] Permitir visualização das definições aplicadas.

---

## Branch: refactor/form-macros

### Componentização
- [ ] Revisar padrões existentes nos templates `form_*`.
- [ ] Criar macros compartilhadas.
- [ ] Remover duplicações.

### Padronização
- [ ] Padronizar Header.
- [ ] Padronizar Inputs.
- [ ] Padronizar Selects.
- [ ] Padronizar Botões.
- [ ] Padronizar Actions Bar.
- [ ] Padronizar Cards.
- [ ] Padronizar Modais.

## Branch: refactor/list-macros

### Componentização
- [ ] Revisar padrões existentes nos templates `list_*`.
- [ ] Criar macros compartilhadas.
- [ ] Remover duplicações.

## Branch: feature/rdo-configuracoes

### Personalização
- [ ] Permitir configuração do formulário por Empresa.
- [ ] Permitir configuração do formulário por Obra.
- [ ] Permitir ocultação de campos.
- [ ] Permitir obrigatoriedade de campos.
- [ ] Permitir configuração de seções.

### Regras
- [ ] Garantir carregamento correto das configurações.
- [ ] Garantir aplicação correta da hierarquia Empresa → Obra.

---

## Branch: refactor/template-rdo

### Correções
- [ ] Corrigir carregamento do campo Tipo conforme cadastro de colaborador.
- [ ] Corrigir desbloqueio do campo Motivo da Parada.
- [ ] Revisar validações do formulário.

### Tabelas Dinâmicas
- [ ] Revisar funcionalidade de inclusão automática de linhas.
- [ ] Verificar impacto no submit.
- [ ] Remover funcionalidade caso necessário.
- [ ] Avaliar substituição por botão "Adicionar Linha". (Já existente)

### Layout
- [ ] Refatorar Header do RDO para seguir padrão dos demais formulários. Exemplo: form_cliente, form_obras...

---

## Branch: fix/list-rdo-acoes

### Backend
- [ ] Passar ID interno do registro para o template.

### Modal de Ações
- [ ] Corrigir corte do modal dentro da tabela.
- [ ] Mover modal para renderização global.
- [ ] Ajustar z-index.
- [ ] Ajustar comportamento de overlay.

### Permissões
- [ ] Exibir todas as ações para todos os papéis.
- [ ] Desabilitar ações sem permissão.
- [ ] Exibir feedback visual para ações indisponíveis.

### Padronização
- [ ] Revisar padrão de ações utilizado nos demais `list_*`.

---

## Branch: fix/responsividade-listagens

### Tabelas
- [ ] Revisar responsividade das tabelas.
- [ ] Garantir que não ultrapassem o container pai.
- [ ] Implementar scroll horizontal quando necessário.

### Layout
- [ ] Revisar comportamento em Desktop.
- [ ] Revisar comportamento em Tablet.
- [ ] Revisar comportamento em Mobile.

### Busca
- [ ] Padronizar input de busca dos `list_*`.
- [ ] Utilizar mesmo componente visual dos formulários.
- [ ] Padronizar espaçamentos e comportamento visual.

---

## Branch: feature/auditoria-workflow

### Auditoria
- [ ] Criar histórico de execução do workflow.
- [ ] Registrar aprovações.
- [ ] Registrar reprovações.
- [ ] Registrar assinaturas.
- [ ] Registrar alterações de status.

### Histórico
- [ ] Criar timeline de eventos do RDO.
- [ ] Exibir usuário responsável por cada ação.
- [ ] Exibir data e hora das ações.

### Rastreabilidade
- [x] Garantir que alterações futuras de workflow não impactem execuções já iniciadas.

## Branch: feature/workflow-resolucao-obra-usuario
- [x] Resolver aprovadores do tipo PAPEL via `obra_usuario`.
- [x] Tratar `workflow_responsaveis` como estrutura legada/opcional.
- [x] Ajustar seeds para depender de `obra_usuario` na matriz principal.
