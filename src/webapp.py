"""
Interface web do SsaTriagemIntimacoes — upload da planilha bruta, geração
da planilha organizada e download, com login simples. Não existe cadastro
público: usuários só existem se criados via manage_users.py (CLI) ou pela
rota /admin/usuarios (exige usuário logado com is_admin=True).

Rodar (a partir da raiz do projeto):
    uvicorn src.webapp:app --reload
"""

import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
import main as pipeline
import usuarios_db

TAMANHO_MINIMO_SENHA = 6

SECRET_KEY = os.getenv("SSA_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "chave-de-desenvolvimento-nao-usar-em-producao"
    print(
        "AVISO: variável de ambiente SSA_SECRET_KEY não definida — usando chave "
        "de desenvolvimento. Defina SSA_SECRET_KEY antes de expor este serviço "
        "(Ngrok, VPS etc.)."
    )

app = FastAPI(title="SsaTriagemIntimacoes")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

_NOME_INVALIDO = re.compile(r"[^A-Za-z0-9._-]")


def _nome_arquivo_seguro(nome_original: str) -> str:
    nome = Path(nome_original or "arquivo.xlsx").name
    nome = _NOME_INVALIDO.sub("_", nome)
    return nome or "arquivo.xlsx"


def _exigir_login(request: Request):
    """Retorna o usuário da sessão, ou um RedirectResponse pra /login."""
    usuario = request.session.get("usuario")
    if not usuario:
        return None, RedirectResponse("/login", status_code=303)
    return usuario, None


def _exigir_admin(request: Request):
    """
    Primeiro checa sessão válida (redireciona pra /login se não tiver),
    depois checa is_admin (retorna 403 se logado mas não-admin — a pessoa
    está autenticada, só não autorizada, então não faz sentido redirecionar
    pro login de novo).
    """
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return None, redirecionamento
    if not usuarios_db.eh_admin(usuario):
        return None, PlainTextResponse("Acesso restrito a administradores.", status_code=403)
    return usuario, None


@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"erro": None})


@app.post("/login")
def login_submit(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    if usuarios_db.verificar_usuario(usuario, senha):
        request.session["usuario"] = usuario.strip()
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "login.html", {"erro": "Usuário ou senha inválidos."}, status_code=401
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
def index(request: Request):
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return redirecionamento
    return templates.TemplateResponse(
        request,
        "index.html",
        {"usuario": usuario, "eh_admin": usuarios_db.eh_admin(usuario), "resultado": None, "erro": None},
    )


@app.post("/processar")
async def processar(request: Request, arquivo: UploadFile = File(...)):
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return redirecionamento

    eh_admin = usuarios_db.eh_admin(usuario)

    if not arquivo.filename.lower().endswith(".xlsx"):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"usuario": usuario, "eh_admin": eh_admin, "resultado": None, "erro": "Envie um arquivo .xlsx."},
            status_code=400,
        )

    config.PASTA_INPUT.mkdir(parents=True, exist_ok=True)
    prefixo = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
    nome_entrada = f"{prefixo}_{_nome_arquivo_seguro(arquivo.filename)}"
    caminho_entrada = config.PASTA_INPUT / nome_entrada

    conteudo = await arquivo.read()
    caminho_entrada.write_bytes(conteudo)

    try:
        resultado = pipeline.processar_planilha(caminho_entrada)
    except Exception as erro:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "usuario": usuario,
                "eh_admin": eh_admin,
                "resultado": None,
                "erro": f"Não foi possível processar o arquivo: {erro}",
            },
            status_code=400,
        )

    return templates.TemplateResponse(
        request, "index.html", {"usuario": usuario, "eh_admin": eh_admin, "resultado": resultado, "erro": None}
    )


@app.get("/download/{nome_arquivo}")
def download(request: Request, nome_arquivo: str):
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return redirecionamento

    pasta_saida = config.PASTA_OUTPUT.resolve()
    caminho = (pasta_saida / nome_arquivo).resolve()

    if not caminho.is_relative_to(pasta_saida) or not caminho.is_file():
        return RedirectResponse("/", status_code=303)

    return FileResponse(caminho, filename=caminho.name)


def _pagina_admin(request: Request, usuario: str, mensagem: str | None, erro: str | None, status_code: int = 200):
    return templates.TemplateResponse(
        request,
        "admin_usuarios.html",
        {
            "usuario": usuario,
            "eh_admin": True,
            "usuarios": usuarios_db.listar_usuarios(),
            "mensagem": mensagem,
            "erro": erro,
        },
        status_code=status_code,
    )


@app.get("/admin/usuarios")
def admin_usuarios(request: Request):
    usuario, resposta = _exigir_admin(request)
    if resposta:
        return resposta
    return _pagina_admin(request, usuario, mensagem=None, erro=None)


@app.post("/admin/usuarios/criar")
def admin_criar_usuario(
    request: Request,
    novo_usuario: str = Form(""),
    nova_senha: str = Form(""),
    is_admin: bool = Form(False),
):
    usuario, resposta = _exigir_admin(request)
    if resposta:
        return resposta

    nome_limpo = novo_usuario.strip()
    if not nome_limpo:
        return _pagina_admin(request, usuario, mensagem=None, erro="O nome de usuário não pode ser vazio.", status_code=400)
    if len(nova_senha) < TAMANHO_MINIMO_SENHA:
        return _pagina_admin(
            request,
            usuario,
            mensagem=None,
            erro=f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.",
            status_code=400,
        )

    try:
        usuarios_db.criar_usuario(nome_limpo, nova_senha, is_admin=is_admin)
    except ValueError as erro:
        return _pagina_admin(request, usuario, mensagem=None, erro=str(erro), status_code=400)

    return _pagina_admin(request, usuario, mensagem=f'Usuário "{nome_limpo}" criado com sucesso.', erro=None)


@app.post("/admin/usuarios/remover/{alvo}")
def admin_remover_usuario(request: Request, alvo: str):
    usuario, resposta = _exigir_admin(request)
    if resposta:
        return resposta

    if alvo.strip() == usuario:
        return _pagina_admin(
            request, usuario, mensagem=None, erro="Você não pode remover o próprio usuário.", status_code=400
        )

    if usuarios_db.remover_usuario(alvo):
        return _pagina_admin(request, usuario, mensagem=f'Usuário "{alvo}" removido.', erro=None)

    return _pagina_admin(request, usuario, mensagem=None, erro=f'Usuário "{alvo}" não encontrado.', status_code=400)