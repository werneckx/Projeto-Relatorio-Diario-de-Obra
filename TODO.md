# TODO - feat/notificacoes (Integrar no cabecalho, dashboard e workflow)
# 🏁 Finalizado - feat/notificacoes

- [ ] (1) Criar `app/services/notificacao_service.py`
  - [ ] criar helper `criar_notificacao(...)`
  - [ ] listar `listar_nao_lidas(usuario_id, empresa_id)`
  - [ ] listar `listar_por_usuario(usuario_id, empresa_id)`
  - [ ] marcar como lida `marcar_como_lida(notificacao_id, usuario_id)`
- [ ] (2) Integrar context processor para o `base.html`
  - [ ] injetar `notifications = {"nao_lidas": [...]}` filtrando `empresa_id`, `usuario_id`, `lida=False` e `ativo=True`
- [ ] (3) Criar rotas (blueprint) para notificações
  - [ ] `GET /notificacoes` (opcional) listar
  - [ ] `POST /notificacoes/<id>/lida` marcar como lida (JSON)
- [ ] (4) Ajustar UI do dropdown no `app/templates/base.html`
  - [ ] adicionar botão/link “marcar como lida” para cada notificação
  - [ ] adicionar JS para chamar o endpoint e atualizar contador/lista (mínimo: recarregar página)
- [ ] (5) Gerar notificações nos eventos de workflow
  - [ ] Em `app/routes/rdo_assinaturas.py`
    - [ ] no `/aprovar-rdo`: quando RDO passa para APROVADO -> `tipo='RDO_APROVADO'` para o criador do RDO
    - [ ] no `/aprovar-rdo`: quando ainda houver próximo aprovador -> `tipo='APROVACAO_PENDENTE'` para o próximo aprovador
    - [ ] no `/rejeitar-rdo`: `tipo='REJEICAO'` para o criador do RDO
    - [ ] no `/salvar-workflow`: criar `tipo='APROVACAO_PENDENTE'` para aprovadores criados (fila inicial)
  - [ ] (mapping definido) `APROVACAO_PENDENTE`, `RDO_APROVADO`, `REJEICAO`, reservar `NOVO_RDO` para criação real do RDO (não implementar agora)
- [ ] (6) Cobrir com testes
  - [ ] `tests/test_notificacoes.py` cobrindo criar/listar/marcar_como_lida
  - [ ] garantir filtro por `empresa_id` e `usuario_id`
- [ ] (7) Rodar `pytest -q` e corrigir falhas
[x] (1) Serviço `NotificacaoService` adaptado ao modelo final.
[x] (2) Context Processor integrado ao `base.html` via sessão.
[x] (3) Rotas de leitura de notificações com validação de segurança.
[x] (4) UI atualizada para processamento assíncrono (AJAX).
[x] (5) Geração automática de notificações no Workflow (Aprovação, Próxima Etapa e Rejeição).
[x] (6) Suíte de testes validando isolamento multi-empresa.
[x] (7) Validação concluída.
