- [ ] Editar `.gitignore`: ignorar `data/**/*.sql`, `data/backups/`, e adicionar `.venv/`
- [ ] Editar `config.py`: remover fallback fixo do `SECRET_KEY` e lançar `RuntimeError` se não estiver no ambiente
- [x] Procurar/criar `.env.example` e garantir que documenta `SECRET_KEY`

- [ ] (Se necessário) Orientar remoção do SQL sensível do tracking (`git rm --cached ...`) e avaliar reescrita de histórico (`git filter-repo`)
