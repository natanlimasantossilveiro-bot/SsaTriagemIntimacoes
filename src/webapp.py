"""
Interface web do SsaTriagemIntimacoes — upload da planilha bruta, geração
da planilha organizada e download, com login simples (usuários só existem
se criados via manage_users.py).

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
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
import main as pipeline
import usuarios_db

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
    return templates.TemplateResponse(request, "index.html", {"usuario": usuario, "resultado": None, "erro": None})


@app.post("/processar")
async def processar(request: Request, arquivo: UploadFile = File(...)):
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return redirecionamento

    if not arquivo.filename.lower().endswith(".xlsx"):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"usuario": usuario, "resultado": None, "erro": "Envie um arquivo .xlsx."},
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
            {"usuario": usuario, "resultado": None, "erro": f"Não foi possível processar o arquivo: {erro}"},
            status_code=400,
        )

    return templates.TemplateResponse(request, "index.html", {"usuario": usuario, "resultado": resultado, "erro": None})


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