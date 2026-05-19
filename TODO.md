# TODO - Ajuste de Login (redirect volta ao /login)

## Passos
- [x] Levantar causa provável no código (middleware invalidando sessão).
- [ ] Adicionar logs temporários no `app/middleware/sessao_middleware.py` para identificar por que a sessão some.
- [ ] Ajustar validação da sessão para compatibilidade com o que o `auth.py` grava (token_hash/expiração/timezone).
- [ ] Remover (ou manter controlado por flag) os logs temporários após confirmação.
- [ ] Validar fluxo: POST /login -> redirect /inicio -> permanecer autenticado.

