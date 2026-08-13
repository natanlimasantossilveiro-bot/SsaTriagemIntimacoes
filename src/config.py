"""
Configurações do SsaTriagemIntimacoes.

Ajuste a lista de palavras-chave e os parâmetros de prioridade aqui,
sem precisar mexer no restante do código.
"""

# TODO: lista definitiva sai da reunião com a solicitante.
# Busca é feita (case-insensitive) no texto da coluna "Conteúdo".
PALAVRAS_CHAVE = [
    # "urgente",
    # "penhora",
    # "audiencia",
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

# Colunas de prazo (podem vir vazias — nesse caso, tratar como sem prazo
# estruturado; ver extração via regex no Conteúdo em main.py)
COLUNA_PRAZO_INICIAL = "Prazo inicial"
COLUNA_PRAZO_FINAL = "Prazo final"
