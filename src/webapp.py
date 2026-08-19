"""
Interface web do SsaTriagemIntimacoes — upload da planilha bruta, geração
da planilha organizada e download, e uma tela de triagem (/intimacoes) que
mostra as intimações já processadas direto na página (via intimacoes_db),
permitindo marcar cada uma como tratada sem precisar reabrir a planilha.
Login simples. Não existe cadastro público: usuários só existem se criados
via manage_users.py (CLI) ou pela rota /admin/usuarios (exige is_admin=True).

Rodar (a partir da raiz do projeto):
    uvicorn src.webapp:app --reload
"""

import os
import re
import secrets
import sys
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
import intimacoes_db
import main as pipeline
import usuarios_db

TAMANHO_MINIMO_SENHA = 6

# alfabeto sem caracteres fáceis de confundir (0/O, 1/l/I) — a senha temporária
# vai ser lida e digitada por uma pessoa, então precisa ser transcritível.
_ALFABETO_SENHA_TEMPORARIA = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


def _gerar_senha_temporaria(tamanho: int = 12) -> str:
    return "".join(secrets.choice(_ALFABETO_SENHA_TEMPORARIA) for _ in range(tamanho))

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
        {
            "usuario": usuario,
            "eh_admin": usuarios_db.eh_admin(usuario),
            "resultado": None,
            "resumo_intimacoes": None,
            "urgentes": intimacoes_db.contar_urgentes(),
            "erro": None,
        },
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
            {
                "usuario": usuario,
                "eh_admin": eh_admin,
                "resultado": None,
                "resumo_intimacoes": None,
                "urgentes": intimacoes_db.contar_urgentes(),
                "erro": "Envie um arquivo .xlsx.",
            },
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
                "resumo_intimacoes": None,
                "urgentes": intimacoes_db.contar_urgentes(),
                "erro": f"Não foi possível processar o arquivo: {erro}",
            },
            status_code=400,
        )

    resumo_intimacoes = intimacoes_db.upsert_intimacoes(resultado.df)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "usuario": usuario,
            "eh_admin": eh_admin,
            "resultado": resultado,
            "resumo_intimacoes": resumo_intimacoes,
            "urgentes": intimacoes_db.contar_urgentes(),
            "erro": None,
        },
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


def _pagina_admin(
    request: Request,
    usuario: str,
    mensagem: str | None,
    erro: str | None,
    status_code: int = 200,
    senha_gerada: str | None = None,
    alvo_senha_gerada: str | None = None,
):
    return templates.TemplateResponse(
        request,
        "admin_usuarios.html",
        {
            "usuario": usuario,
            "eh_admin": True,
            "usuarios": usuarios_db.listar_usuarios(),
            "mensagem": mensagem,
            "erro": erro,
            "senha_gerada": senha_gerada,
            "alvo_senha_gerada": alvo_senha_gerada,
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


@app.post("/admin/usuarios/redefinir-senha/{alvo}")
def admin_redefinir_senha(request: Request, alvo: str, senha_escolhida: str = Form("")):
    usuario, resposta = _exigir_admin(request)
    if resposta:
        return resposta

    senha_escolhida = senha_escolhida.strip()
    if senha_escolhida and len(senha_escolhida) < TAMANHO_MINIMO_SENHA:
        return _pagina_admin(
            request,
            usuario,
            mensagem=None,
            erro=f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.",
            status_code=400,
        )

    # se o admin não digitar nada, gera uma senha aleatória (mostrada uma vez na tela).
    nova_senha = senha_escolhida or _gerar_senha_temporaria()
    if not usuarios_db.redefinir_senha(alvo, nova_senha):
        return _pagina_admin(request, usuario, mensagem=None, erro=f'Usuário "{alvo}" não encontrado.', status_code=400)

    if senha_escolhida:
        return _pagina_admin(request, usuario, mensagem=f'Senha de "{alvo}" redefinida com sucesso.', erro=None)
    return _pagina_admin(request, usuario, mensagem=None, erro=None, senha_gerada=nova_senha, alvo_senha_gerada=alvo)


def _redirecionar_intimacoes(aba: str, busca: str) -> RedirectResponse:
    query = urlencode({"aba": aba, "busca": busca})
    return RedirectResponse(f"/intimacoes?{query}", status_code=303)


@app.get("/intimacoes")
def intimacoes(request: Request, aba: str = "pendentes", busca: str = ""):
    """
    Tela de triagem: mostra as intimações já processadas direto na página
    (sem precisar baixar planilha), com opção de marcar cada uma como
    tratada — some da aba "Pendentes" e passa pra "Tratadas".
    """
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return redirecionamento

    busca = busca.strip()
    itens = intimacoes_db.listar_intimacoes(tratada=(aba == "tratadas"), busca=busca)

    return templates.TemplateResponse(
        request,
        "intimacoes.html",
        {
            "usuario": usuario,
            "eh_admin": usuarios_db.eh_admin(usuario),
            "itens": itens,
            "aba": aba,
            "busca": busca,
            "total_pendentes": intimacoes_db.contar_pendentes(),
            "total_tratadas": intimacoes_db.contar_tratadas(),
            "urgentes": intimacoes_db.contar_urgentes(),
        },
    )


@app.post("/intimacoes/{codigo}/tratar")
def intimacoes_tratar(request: Request, codigo: str, aba: str = Form("pendentes"), busca: str = Form("")):
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return redirecionamento
    intimacoes_db.marcar_tratada(codigo, usuario)
    return _redirecionar_intimacoes(aba, busca)


@app.post("/intimacoes/{codigo}/destratar")
def intimacoes_destratar(request: Request, codigo: str, aba: str = Form("tratadas"), busca: str = Form("")):
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return redirecionamento
    intimacoes_db.desmarcar_tratada(codigo)
    return _redirecionar_intimacoes(aba, busca)


@app.get("/minha-senha")
def minha_senha_form(request: Request):
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return redirecionamento
    return templates.TemplateResponse(
        request,
        "minha_senha.html",
        {"usuario": usuario, "eh_admin": usuarios_db.eh_admin(usuario), "erro": None, "sucesso": None},
    )


@app.post("/minha-senha")
def minha_senha_submit(
    request: Request,
    senha_atual: str = Form(""),
    nova_senha: str = Form(""),
    confirmar_senha: str = Form(""),
):
    usuario, redirecionamento = _exigir_login(request)
    if redirecionamento:
        return redirecionamento

    eh_admin = usuarios_db.eh_admin(usuario)

    def pagina(erro=None, sucesso=None, status_code=200):
        return templates.TemplateResponse(
            request,
            "minha_senha.html",
            {"usuario": usuario, "eh_admin": eh_admin, "erro": erro, "sucesso": sucesso},
            status_code=status_code,
        )

    if len(nova_senha) < TAMANHO_MINIMO_SENHA:
        return pagina(erro=f"A nova senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.", status_code=400)
    if nova_senha != confirmar_senha:
        return pagina(erro="A confirmação não bate com a nova senha.", status_code=400)
    if not usuarios_db.alterar_propria_senha(usuario, senha_atual, nova_senha):
        return pagina(erro="Senha atual incorreta.", status_code=401)

    return pagina(sucesso="Senha alterada com sucesso.")