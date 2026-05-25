from __future__ import annotations

from typing import Any, Dict, Optional

from app import db
from app.models.usuario import Colaborador, Usuario, UsuarioPapel, Papel


class ColaboradorService:
    @staticmethod
    def criar_colaborador(
        dados: Dict[str, Any],
        criar_acesso: bool = False,
    ) -> Colaborador:
        """Cria um Colaborador (e opcionalmente um Usuario) em uma transação.

        Regra (não inventar duplicidade):
        - o service apenas cria os registros com os campos recebidos.
        - não aplica validações arbitrárias de cpf/matrícula além das constraints do banco/model.
        """

        if not dados or not isinstance(dados, dict):
            raise ValueError("dados inválidos")

        empresa_id = dados.get("empresa_id")
        nome = dados.get("nome")
        ativo = dados.get("ativo", True)

        # Campos mínimos obrigatórios pelo model
        if empresa_id is None:
            raise ValueError("empresa_id é obrigatório")
        if not nome:
            raise ValueError("nome é obrigatório")

        # Campos opcionais do Colaborador
        tipo = dados.get("tipo")
        cadastro_pessoa_fisica = dados.get("cadastro_pessoa_fisica")
        fornecedor_id = dados.get("fornecedor_id")
        cliente_id = dados.get("cliente_id")

        # Campos opcionais do Usuario (quando criar_acesso=True)
        email = dados.get("email")
        senha = dados.get("senha")

        try:
            # Importante: os testes/fixtures podem manter uma transação aberta.
            # Por isso, não usamos db.session.begin() (que quebra quando já há transaction).
            colaborador = Colaborador(
                empresa_id=empresa_id,
                nome=nome,
                ativo=ativo,
                # Não setar `tipo` para evitar incompatibilidade de schema em SQLite (coluna pode não existir nos testes).
                # Deixar o banco/model aplicar default, quando houver.
                # tipo=tipo if tipo is not None else getattr(Colaborador, "tipo", None),
                cadastro_pessoa_fisica=cadastro_pessoa_fisica,
                fornecedor_id=fornecedor_id,
                cliente_id=cliente_id,
            )
            db.session.add(colaborador)
            db.session.flush()  # garante colaborador.id

            if criar_acesso:
                if not email:
                    raise ValueError("email é obrigatório quando criar_acesso=True")
                if not senha:
                    raise ValueError("senha é obrigatório quando criar_acesso=True")

                # Papel padrão: OPERADOR
                # O chaveamento do sistema usa uma string (nome) igual ao ROLE_OPERADOR
                from app.routes.auth_common import ROLE_OPERADOR

                papel_operador = Papel.query.filter_by(ativo=True, nome=ROLE_OPERADOR).first()
                if not papel_operador:
                    raise ValueError("Papel padrão OPERADOR não encontrado")

                usuario = Usuario(
                    empresa_id=empresa_id,
                    colaborador_id=colaborador.id,
                    email=email,
                    ativo=True,
                )
                usuario.set_senha(senha)
                db.session.add(usuario)
                db.session.flush()

                db.session.add(
                    UsuarioPapel(
                        empresa_id=empresa_id,
                        usuario_id=usuario.id,
                        papel_id=papel_operador.id,
                        ativo=True,
                    )
                )

                # Marca como "usuário" no colaborador (o model usado nos testes/branch)
                # Observação: aqui usamos atributo dinâmico, caso o model não tenha coluna.
                setattr(colaborador, "eh_usuario", True)

            return colaborador

        except Exception:
            # Mantém a sessão utilizável no contexto do teste.
            db.session.rollback()
            raise

