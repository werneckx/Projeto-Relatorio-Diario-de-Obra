# Review: Database Seeds Workflow

## Escopo revisado

- Modelos: `app/models/empresa.py`, `app/models/obra.py`, `app/models/workflow.py`, `app/models/usuario.py`, `app/models/configuracao.py`, `app/models/rdo.py`
- Serviços e rotas: `app/services/workflow_service.py`, `app/routes/admin.py`, `app/routes/empresa.py`, `app/routes/rdo_assinaturas.py`
- Script de banco: `data/Script Banco de Dados.sql`
- Testes: `tests/test_workflow.py`, `tests/test_workflow_admin.py`

## Arquitetura atual

- O relacionamento principal está coerente para o fluxo atual:
  - `Empresa 1:N Obras`
  - `Empresa 1:N WorkflowDefinicao`
  - `Obra 0..N WorkflowDefinicao`
  - `WorkflowDefinicao 1:N WorkflowEtapa`
  - `WorkflowEtapa N:1 Papel` e `WorkflowEtapa N:1 Usuario`
  - `Obra 1:N ObraUsuario` para alocação de responsáveis por obra
- O fallback de workflow já existe no backend via `WorkflowService.resolver_workflow`, com prioridade `Obra -> Empresa`.
- Configuração dinâmica já existe em três níveis:
  - `config_definicoes`
  - `empresa_config`
  - `obra_config`

## O que já é suportado no backend

- Aprovação: suportada em `WorkflowService.aprovar_etapa` e nas rotas legadas de assinatura.
- Reprovação: suportada em `WorkflowService.rejeitar_etapa` e nas rotas legadas.
- Assinatura: suportada hoje pelo fluxo legado em `app/routes/rdo_assinaturas.py` e pelo armazenamento em `rdo_assinaturas` / `rdo_aprovacoes`.
- Reabertura: suportada parcialmente em `WorkflowService.rejeitar_etapa(..., reabrir=True)`.
- Encerramento: existe para sessão de usuário, mas não existe como etapa/estado próprio do workflow ou do RDO além de `APROVADO`, `REJEITADO` e `CANCELADO`.

## Lacunas arquiteturais identificadas

- Há duplicidade de lógica de workflow entre `WorkflowService` e `app/routes/rdo_assinaturas.py`.
- O modelo Python ainda é mais simples que o SQL:
  - o SQL já prevê `tipo_fluxo`, `tipo_aprovador`, `papel_codigo`, `assinatura_obrigatoria`, `permite_reabertura`, `permite_cancelamento`
  - os modelos SQLAlchemy ainda usam apenas `papel_id`, `usuario_aprovador_id`, `obrigatorio` e `sla_horas`
- Não existe uma entidade própria de execução do workflow. Hoje a execução fica implícita em `rdo_aprovacoes`.
- Não existe snapshot formal da definição do workflow no momento de início do fluxo; isso pode impactar rastreabilidade se a definição for alterada depois.
- Não existe matriz persistida de responsáveis por papel em nível de empresa/obra; hoje isso depende de `UsuarioPapel`, `ObraUsuario` e `usuario_responsavel_id`.

## Ajustes aplicados nesta branch

- Corrigida a resolução de aprovador por papel em `WorkflowService`:
  - agora prioriza `usuario_aprovador_id`
  - depois tenta responsável alocado na `obra_usuario`
  - por fim cai para `usuario_papel`
- O script `data/Script Banco de Dados.sql` já continha a maior parte da massa de dados; a revisão desta branch deixa o seed orientado ao workflow configurável como referência do banco.

## Próximos passos recomendados

- Unificar a execução de aprovação/reprovação/assinatura em `WorkflowService`.
- Criar entidade de execução do workflow por RDO, com snapshot das etapas.
- Alinhar os modelos SQLAlchemy aos campos já previstos no script SQL para workflow configurável completo.
- Criar uma matriz explícita de responsáveis por papel em nível empresa/obra.
