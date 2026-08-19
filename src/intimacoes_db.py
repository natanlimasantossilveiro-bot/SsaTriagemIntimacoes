"""
Persistência das intimações processadas — permite tratar (marcar como
resolvida) direto na tela, sem precisar reabrir a planilha exportada.

Chave de identidade: "Código da intimação" (config.COLUNA_CODIGO), único
por intimação em todo o histórico do Publicações Online. Cada upload faz
upsert: intimações novas entram na fila; intimações já vistas antes (ex.:
reprocessar o mesmo arquivo) têm seus dados atualizados sem perder o status
de "tratada".
"""

import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config

_COLUNAS_SELECT = (
    "codigo, processo, termo_pesquisa, data_cadastro, data_evento, prazo_inicial, "
    "prazo_final, conteudo, palavras_chave, peso_palavras, qtde_repeticoes, "
    "conteudo_duplicado, teor_incompleto, origem_prazo, data_limite, prazo_aberto, "
    "sinalizadores, tratada, tratada_por, tratada_em"
)


@dataclass
class Intimacao:
    codigo: str
    processo: str
    termo_pesquisa: str
    data_cadastro: str
    data_evento: str
    prazo_inicial: str
    prazo_final: str
    conteudo: str
    palavras_chave: str
    peso_palavras: int
    qtde_repeticoes: int
    conteudo_duplicado: bool
    teor_incompleto: bool
    origem_prazo: str
    data_limite: str | None
    prazo_aberto: bool
    sinalizadores: str
    tratada: bool
    tratada_por: str | None
    tratada_em: str | None


def _conectar() -> sqlite3.Connection:
    conexao = sqlite3.connect(config.CAMINHO_BANCO_INTIMACOES)
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS intimacoes (
            codigo TEXT PRIMARY KEY,
            processo TEXT,
            termo_pesquisa TEXT,
            data_cadastro TEXT,
            data_evento TEXT,
            prazo_inicial TEXT,
            prazo_final TEXT,
            conteudo TEXT,
            palavras_chave TEXT,
            peso_palavras INTEGER NOT NULL DEFAULT 0,
            qtde_repeticoes INTEGER,
            conteudo_duplicado INTEGER NOT NULL DEFAULT 0,
            teor_incompleto INTEGER NOT NULL DEFAULT 0,
            origem_prazo TEXT,
            data_limite TEXT,
            prazo_aberto INTEGER NOT NULL DEFAULT 0,
            sinalizadores TEXT,
            tratada INTEGER NOT NULL DEFAULT 0,
            tratada_por TEXT,
            tratada_em TEXT,
            importado_em TEXT
        )
        """
    )
    # migração: bancos criados antes da coluna peso_palavras existir.
    colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(intimacoes)")}
    if "peso_palavras" not in colunas:
        conexao.execute("ALTER TABLE intimacoes ADD COLUMN peso_palavras INTEGER NOT NULL DEFAULT 0")
    return conexao


def _valor(row, coluna: str, default: str = "") -> str:
    valor = row.get(coluna)
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return default
    return str(valor).strip()


def upsert_intimacoes(df: pd.DataFrame) -> dict:
    """
    Insere/atualiza as intimações do DataFrame já processado (ver
    main.processar_planilha — espera as colunas que o pipeline adiciona,
    incluindo "Sinalizadores"). Preserva tratada/tratada_por/tratada_em de
    intimações já existentes. Retorna {"novas": N, "atualizadas": N}.
    """
    agora = datetime.now().isoformat(timespec="seconds")
    novas = 0
    atualizadas = 0

    with _conectar() as conexao:
        for _, row in df.iterrows():
            codigo = _valor(row, config.COLUNA_CODIGO)
            if not codigo:
                continue

            data_limite = row.get("Data limite (prazo)")
            data_limite_iso = data_limite.date().isoformat() if pd.notna(data_limite) else None

            existente = conexao.execute("SELECT 1 FROM intimacoes WHERE codigo = ?", (codigo,)).fetchone()

            campos_comuns = (
                _valor(row, config.COLUNA_PROCESSO),
                _valor(row, config.COLUNA_TERMO_PESQUISA),
                _valor(row, config.COLUNA_DATA_CADASTRO),
                _valor(row, config.COLUNA_DATA_EVENTO),
                _valor(row, config.COLUNA_PRAZO_INICIAL),
                _valor(row, config.COLUNA_PRAZO_FINAL),
                _valor(row, config.COLUNA_CONTEUDO),
                _valor(row, "Palavras-chave encontradas"),
                int(row.get("Peso das palavras-chave", 0) or 0),
                int(row.get("Qtde repetições (processo)", 0) or 0),
                int(_valor(row, "Conteúdo duplicado?") == "sim"),
                int(_valor(row, "Teor incompleto?") == "sim"),
                _valor(row, "Origem do prazo"),
                data_limite_iso,
                int(_valor(row, "Prazo em aberto?") == "sim"),
                _valor(row, "Sinalizadores"),
                agora,
            )

            if existente:
                conexao.execute(
                    """
                    UPDATE intimacoes SET
                        processo = ?, termo_pesquisa = ?, data_cadastro = ?, data_evento = ?,
                        prazo_inicial = ?, prazo_final = ?, conteudo = ?, palavras_chave = ?,
                        peso_palavras = ?, qtde_repeticoes = ?, conteudo_duplicado = ?,
                        teor_incompleto = ?, origem_prazo = ?, data_limite = ?, prazo_aberto = ?,
                        sinalizadores = ?, importado_em = ?
                    WHERE codigo = ?
                    """,
                    campos_comuns + (codigo,),
                )
                atualizadas += 1
            else:
                conexao.execute(
                    """
                    INSERT INTO intimacoes (
                        processo, termo_pesquisa, data_cadastro, data_evento,
                        prazo_inicial, prazo_final, conteudo, palavras_chave,
                        peso_palavras, qtde_repeticoes, conteudo_duplicado, teor_incompleto,
                        origem_prazo, data_limite, prazo_aberto, sinalizadores,
                        importado_em, codigo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    campos_comuns + (codigo,),
                )
                novas += 1

    return {"novas": novas, "atualizadas": atualizadas}


def _para_intimacao(linha) -> Intimacao:
    return Intimacao(
        codigo=linha[0],
        processo=linha[1],
        termo_pesquisa=linha[2],
        data_cadastro=linha[3],
        data_evento=linha[4],
        prazo_inicial=linha[5],
        prazo_final=linha[6],
        conteudo=linha[7],
        palavras_chave=linha[8],
        peso_palavras=linha[9] or 0,
        qtde_repeticoes=linha[10] or 0,
        conteudo_duplicado=bool(linha[11]),
        teor_incompleto=bool(linha[12]),
        origem_prazo=linha[13],
        data_limite=linha[14],
        prazo_aberto=bool(linha[15]),
        sinalizadores=linha[16],
        tratada=bool(linha[17]),
        tratada_por=linha[18],
        tratada_em=linha[19],
    )


def listar_intimacoes(tratada: bool = False, busca: str = "") -> list[Intimacao]:
    """
    Lista intimações pendentes (tratada=False) ou já tratadas (tratada=True).
    Mesmo critério de main.calcular_prioridade: agrupa por processo (o grupo
    aparece na posição da sua intimação mais urgente — menor data-limite,
    maior peso de palavra-chave em caso de empate), e dentro do grupo ordena
    pela data-limite de cada linha, com o peso como desempate final.
    """
    sql = f"""
        SELECT {_COLUNAS_SELECT}
        FROM intimacoes
        WHERE tratada = ?
    """
    parametros: list = [int(tratada)]

    if busca:
        termo = f"%{busca}%"
        sql += " AND (processo LIKE ? OR conteudo LIKE ? OR termo_pesquisa LIKE ?)"
        parametros += [termo, termo, termo]

    # window functions calculadas sobre o resultado já filtrado (WHERE roda
    # antes): grupo_data_limite/grupo_peso resumem a intimação mais urgente
    # de cada processo, dentro do que sobrou depois do filtro/busca.
    sql = f"""
        SELECT *, MIN(data_limite) OVER (PARTITION BY processo) AS grupo_data_limite,
                  MAX(peso_palavras) OVER (PARTITION BY processo) AS grupo_peso
        FROM ({sql})
        ORDER BY
            (grupo_data_limite IS NULL), grupo_data_limite ASC,
            grupo_peso DESC,
            processo ASC,
            (data_limite IS NULL), data_limite ASC,
            peso_palavras DESC
    """

    with _conectar() as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()

    return [_para_intimacao(linha) for linha in linhas]


def contar_pendentes() -> int:
    with _conectar() as conexao:
        return conexao.execute("SELECT COUNT(*) FROM intimacoes WHERE tratada = 0").fetchone()[0]


def contar_tratadas() -> int:
    with _conectar() as conexao:
        return conexao.execute("SELECT COUNT(*) FROM intimacoes WHERE tratada = 1").fetchone()[0]


def contar_urgentes(dias: int = config.DIAS_ALERTA_PRAZO) -> int:
    """
    Pendentes com data-limite já vencida ou vencendo em até `dias` dias.
    Usada pro alerta de prazo nas telas — ver config.DIAS_ALERTA_PRAZO.
    """
    limite = (date.today() + timedelta(days=dias)).isoformat()
    with _conectar() as conexao:
        return conexao.execute(
            "SELECT COUNT(*) FROM intimacoes WHERE tratada = 0 AND data_limite IS NOT NULL AND data_limite <= ?",
            (limite,),
        ).fetchone()[0]


def marcar_tratada(codigo: str, usuario: str) -> bool:
    agora = datetime.now().isoformat(timespec="seconds")
    with _conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE intimacoes SET tratada = 1, tratada_por = ?, tratada_em = ? WHERE codigo = ?",
            (usuario, agora, codigo),
        )
        return cursor.rowcount > 0


def desmarcar_tratada(codigo: str) -> bool:
    with _conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE intimacoes SET tratada = 0, tratada_por = NULL, tratada_em = NULL WHERE codigo = ?",
            (codigo,),
        )
        return cursor.rowcount > 0
