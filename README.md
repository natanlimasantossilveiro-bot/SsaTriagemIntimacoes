# SsaTriagemIntimacoes

Ferramenta interna da SSA para organizar as planilhas de intimações extraídas
do sistema **Publicações Online**, deixando o arquivo mais limpo e fácil de
ler no dia a dia, sem alterar os dados originais.

## Contexto

O sistema Publicações Online captura apenas os painéis eletrônicos dos
advogados (não inclui diários nem movimentações). O relatório bruto sai como
`.xlsx` com uma aba `Resumo` e uma aba `Relatório` (dados linha a linha).

Esse projeto lê esse arquivo bruto e gera uma **planilha nova** (o original
nunca é alterado) com:

1. **Palavras-chave** — busca no texto da coluna `Conteúdo` (teor da
   intimação) e sinaliza as linhas que contêm termos relevantes.
2. **Ordem de importância** — ordena por data (`Data de
   disponibilização/evento`) e por situação do prazo (prazo em aberto tem
   prioridade).
3. **Processos repetidos** — sinaliza quando o mesmo `Nº do processo`
   aparece mais de uma vez no dia, com contagem de repetições. Também
   sinaliza quando o *conteúdo* do texto se repete entre linhas, mesmo que o
   processo seja diferente.
4. **Itens com teor incompleto** — a aba `Resumo` às vezes lista códigos de
   intimação que o sistema não conseguiu exportar por completo. Essas linhas
   são marcadas separadamente na saída, pra não passarem batido.

## Escopo confirmado com a solicitante (13/08/2026)

- Palavras-chave: lista inicial a definir em reunião (ver `src/config.py`).
- Critério de prioridade: data do evento + prazo em aberto.
- Busca de palavra-chave: apenas no texto da coluna `Conteúdo`.
- Repetição: marcar linha + coluna com quantidade de repetições; sinalizar
  também repetição de conteúdo.
- Sem SharePoint por enquanto — output local, pasta da controladoria futura.

## Estrutura

```
SsaTriagemIntimacoes/
├── input/          # coloque aqui o .xlsx bruto extraído do Publicações Online
├── output/         # planilha organizada é gerada aqui
├── src/
│   ├── config.py   # lista de palavras-chave e parâmetros ajustáveis
│   └── main.py     # script principal
├── tests/
└── requirements.txt
```

## Uso

```bash
pip install -r requirements.txt
python src/main.py input/NOME_DO_ARQUIVO.xlsx
```

Gera `output/NOME_DO_ARQUIVO_organizado.xlsx`.
