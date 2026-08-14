"""
Banco de usuários do webapp (SQLite local, arquivo config.CAMINHO_BANCO_USUARIOS).

Não existe cadastro público — usuários só são criados pelo admin, via
manage_users.py (CLI) ou pela rota /admin/usuarios (webapp, exige admin
logado). Este módulo é a única fonte de lógica de hash/criação/remoção,
compartilhada pelos dois.
"""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from passlib.context import CryptContext

import config

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class Usuario:
    username: str
    is_admin: bool


def _conectar() -> sqlite3.Connection:
    conexao = sqlite3.connect(config.CAMINHO_BANCO_USUARIOS)
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    # migração: bancos criados antes da coluna is_admin existir.
    colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(usuarios)")}
    if "is_admin" not in colunas:
        conexao.execute("ALTER TABLE usuarios ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    return conexao


def criar_usuario(username: str, senha: str, is_admin: bool = False) -> bool:
    """
    Cria o usuário e retorna se ele ficou admin. O primeiro usuário da
    tabela vira admin automaticamente, mesmo sem is_admin=True explícito.
    """
    username = username.strip()
    with _conectar() as conexao:
        existente = conexao.execute(
            "SELECT 1 FROM usuarios WHERE username = ?", (username,)
        ).fetchone()
        if existente:
            raise ValueError(f'Usuário "{username}" já existe.')

        total_usuarios = conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        eh_admin = is_admin or total_usuarios == 0

        conexao.execute(
            "INSERT INTO usuarios (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, _pwd_context.hash(senha), int(eh_admin)),
        )
    return eh_admin


def verificar_usuario(username: str, senha: str) -> bool:
    with _conectar() as conexao:
        linha = conexao.execute(
            "SELECT password_hash FROM usuarios WHERE username = ?", (username.strip(),)
        ).fetchone()
    if not linha:
        return False
    return _pwd_context.verify(senha, linha[0])


def eh_admin(username: str) -> bool:
    with _conectar() as conexao:
        linha = conexao.execute(
            "SELECT is_admin FROM usuarios WHERE username = ?", (username.strip(),)
        ).fetchone()
    return bool(linha and linha[0])


def listar_usuarios() -> list[Usuario]:
    with _conectar() as conexao:
        linhas = conexao.execute(
            "SELECT username, is_admin FROM usuarios ORDER BY username"
        ).fetchall()
    return [Usuario(username=linha[0], is_admin=bool(linha[1])) for linha in linhas]


def remover_usuario(username: str) -> bool:
    with _conectar() as conexao:
        cursor = conexao.execute("DELETE FROM usuarios WHERE username = ?", (username.strip(),))
        return cursor.rowcount > 0


def redefinir_senha(username: str, nova_senha: str) -> bool:
    """Troca a senha do usuário sem exigir a senha atual (uso do admin, via /admin/usuarios). Retorna se ele existia."""
    with _conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE usuarios SET password_hash = ? WHERE username = ?",
            (_pwd_context.hash(nova_senha), username.strip()),
        )
        return cursor.rowcount > 0


def alterar_propria_senha(username: str, senha_atual: str, nova_senha: str) -> bool:
    """
    Troca a própria senha do usuário logado, exigindo a senha atual correta
    (diferente de redefinir_senha, que é o admin resetando a senha de
    outra pessoa sem precisar sabê-la). Retorna False se a senha atual não
    confere — nesse caso nada é alterado.
    """
    if not verificar_usuario(username, senha_atual):
        return False
    redefinir_senha(username, nova_senha)
    return True
