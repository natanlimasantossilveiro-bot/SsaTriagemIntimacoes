"""
Gerenciamento de usuários do webapp — não existe cadastro público, só o
admin cria/remove usuários por aqui.

Uso:
    python src/manage_users.py criar <usuario>
    python src/manage_users.py listar
    python src/manage_users.py remover <usuario>
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import usuarios_db


def cmd_criar(args):
    senha = getpass.getpass("Senha: ")
    confirmacao = getpass.getpass("Confirme a senha: ")
    if senha != confirmacao:
        print("As senhas não coincidem.")
        sys.exit(1)
    if not senha:
        print("Senha não pode ser vazia.")
        sys.exit(1)
    try:
        usuarios_db.criar_usuario(args.usuario, senha)
    except ValueError as erro:
        print(erro)
        sys.exit(1)
    print(f'Usuário "{args.usuario}" criado com sucesso.')


def cmd_listar(args):
    usuarios = usuarios_db.listar_usuarios()
    if not usuarios:
        print("Nenhum usuário cadastrado.")
        return
    for usuario in usuarios:
        print(usuario)


def cmd_remover(args):
    removido = usuarios_db.remover_usuario(args.usuario)
    if removido:
        print(f'Usuário "{args.usuario}" removido.')
    else:
        print(f'Usuário "{args.usuario}" não encontrado.')
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Gerenciar usuários do webapp SsaTriagemIntimacoes.")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    parser_criar = subparsers.add_parser("criar", help="Cria um novo usuário (senha pedida via prompt).")
    parser_criar.add_argument("usuario")
    parser_criar.set_defaults(func=cmd_criar)

    parser_listar = subparsers.add_parser("listar", help="Lista os usuários cadastrados.")
    parser_listar.set_defaults(func=cmd_listar)

    parser_remover = subparsers.add_parser("remover", help="Remove um usuário existente.")
    parser_remover.add_argument("usuario")
    parser_remover.set_defaults(func=cmd_remover)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()