"""
Banco de usuários do webapp (SQLite local, arquivo config.CAMINHO_BANCO_USUARIOS).

Não existe cadastro público — usuários só são criados pelo admin via
manage_users.py. Este módulo é compartilhado por manage_users.py (CLI) e
webapp.py (autenticação das rotas).
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from passlib.context import CryptContext

import config

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _conectar() -> sqlite3.Connection:
    conexao = sqlite3.connect(config.CAMINHO_BANCO_USUARIOS)
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
        """
    )
    return conexao


def criar_usuario(username: str, senha: str) -> None:
    username = username.strip()
    with _conectar() as conexao:
        existente = conexao.execute(
            "SELECT 1 FROM usuarios WHERE username = ?", (username,)
        ).fetchone()
        if existente:
            raise ValueError(f'Usuário "{username}" já existe.')
        conexao.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES (?, ?)",
            (username, _pwd_context.hash(senha)),
        )


def verificar_usuario(username: str, senha: str) -> bool:
    with _conectar() as conexao:
        linha = conexao.execute(
            "SELECT password_hash FROM usuarios WHERE username = ?", (username.strip(),)
        ).fetchone()
    if not linha:
        return False
    return _pwd_context.verify(senha, linha[0])


def listar_usuarios() -> list[str]:
    with _conectar() as conexao:
        linhas = conexao.execute("SELECT username FROM usuarios ORDER BY username").fetchall()
    return [linha[0] for linha in linhas]


def remover_usuario(username: str) -> bool:
    with _conectar() as conexao:
        cursor = conexao.execute("DELETE FROM usuarios WHERE username = ?", (username.strip(),))
        return cursor.rowcount > 0