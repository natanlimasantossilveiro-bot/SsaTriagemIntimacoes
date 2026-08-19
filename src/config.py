"""
Configurações do SsaTriagemIntimacoes.

Ajuste a lista de palavras-chave e os parâmetros de prioridade aqui,
sem precisar mexer no restante do código.
"""

from pathlib import Path

# Pastas de entrada/saída (relativas à raiz do projeto — tanto o CLI quanto
# o webapp devem ser executados a partir da raiz).
PASTA_INPUT = Path("input")
PASTA_OUTPUT = Path("output")

# Bancos locais do webapp (nunca versionados — ver .gitignore).
CAMINHO_BANCO_USUARIOS = Path(__file__).resolve().parent / "usuarios.db"
CAMINHO_BANCO_INTIMACOES = Path(__file__).resolve().parent / "intimacoes.db"

# Intimações pendentes com prazo vencendo em até essa quantidade de dias (ou
# já vencido) disparam o alerta de prazo na tela — ver intimacoes_db.contar_urgentes.
DIAS_ALERTA_PRAZO = 3

# TODO: lista definitiva sai da reunião com a solicitante.
# Busca é feita (case-insensitive) no texto da coluna "Conteúdo".
# Cada termo tem um peso (quanto maior, mais prioridade dá pra intimação que
# contém aquele termo). A soma dos pesos das palavras encontradas numa linha
# é usada como desempate na ordenação — o prazo continua sendo o critério
# principal, o peso só decide entre linhas com prazo parecido (ver
# calcular_prioridade em main.py). Formato: (termo, peso).
PALAVRAS_CHAVE = [
    # ("urgente", 10),
    # ("penhora", 5),
    # ("audiencia", 3),
]

# Nome da aba de dados dentro do xlsx bruto do Publicações Online
ABA_DADOS = "Relatório"
ABA_RESUMO = "Resumo"

# Linha (1-indexed) onde está o cabeçalho real dentro da aba de dados
LINHA_CABECALHO = 2

# Coluna onde a busca de palavra-chave é feita
COLUNA_CONTEUDO = "Conteúdo"

# Coluna com o código único da intimação (usada para cruzar com a aba Resumo)
COLUNA_CODIGO = "Código da intimação"

# Coluna usada para identificar processos repetidos
COLUNA_PROCESSO = "Nº do processo"

# Coluna usada para ordenar por data (critério de prioridade)
COLUNA_DATA_EVENTO = "Data de disponibilização/evento"

# Colunas extras exibidas na tela de intimações (/intimacoes)
COLUNA_TERMO_PESQUISA = "Termo de pesquisa"
COLUNA_DATA_CADASTRO = "Data de cadastro"

# Colunas de prazo (podem vir vazias — nesse caso, tratar como sem prazo
# estruturado; ver extração via regex no Conteúdo em main.py)
COLUNA_PRAZO_INICIAL = "Prazo inicial"
COLUNA_PRAZO_FINAL = "Prazo final"
