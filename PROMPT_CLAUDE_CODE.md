# Prompt para o Claude Code

Cole o texto abaixo no Claude Code assim que abrir o projeto no VSCode.

---

Este projeto (`SsaTriagemIntimacoes`) organiza planilhas de intimações
extraídas do sistema **Publicações Online**. O objetivo é ler o `.xlsx`
bruto e gerar uma planilha nova, mais limpa e priorizada, sem alterar o
arquivo original.

Leia `README.md` para o contexto completo e `src/config.py` para os
parâmetros ajustáveis. Já existe um arquivo de exemplo real em
`input/Doc-102_intimações_13-08-2026.xlsx` — use-o para testar.

## Estrutura do arquivo de entrada

O `.xlsx` bruto tem duas abas:

- **Resumo**: metadados do relatório. A partir da linha que contém o texto
  "Código dos itens com teor incompleto e/ou não exportado:", as linhas
  seguintes trazem uma mini-tabela com duas colunas: `Código da intimação` e
  `Nº do processo` — são os itens que o sistema falhou em exportar por
  completo. Essa seção pode não existir (nem toda planilha tem itens
  incompletos) — trate isso sem quebrar.
- **Relatório**: os dados linha a linha. O cabeçalho real está na **linha 2**
  (a linha 1 vem vazia). Colunas relevantes: `Seq.`, `Código da intimação`,
  `Nº do processo`, `Termo de pesquisa`, `Data de cadastro`, `Data de
  disponibilização/evento`, `Prazo inicial`, `Prazo final`, `Conteúdo`.

Implemente as funções já esqueletadas em `src/main.py`, seguindo os
`TODO`s de cada uma. Detalhamento de cada etapa:

### 1. `carregar_planilha_bruta`
Ler as duas abas. Da aba Resumo, extrair a lista de códigos de intimação
marcados como teor incompleto (pode ser lista vazia). Retornar um
DataFrame da aba Relatório + essa lista de códigos incompletos.

### 2. `marcar_palavras_chave`
Buscar cada termo de `config.PALAVRAS_CHAVE` dentro da coluna `Conteúdo`
(case-insensitive, ignorando acentos se possível). A lista está vazia por
enquanto (aguardando reunião com a solicitante) — o código deve funcionar
normalmente mesmo com a lista vazia (nenhuma linha marcada). Adicionar
coluna `Palavras-chave encontradas` com os termos que bateram, separados
por vírgula.

### 3. `marcar_repetidos`
- Agrupar por `Nº do processo`, contar ocorrências, adicionar coluna
  `Qtde repetições (processo)`.
- Também comparar o texto de `Conteúdo` entre linhas de processos
  DIFERENTES: se o texto for idêntico (ou muito similar — pode usar
  comparação exata para começar), marcar `Conteúdo duplicado?` = sim.

### 4. `marcar_teor_incompleto`
Marcar `Teor incompleto?` = sim para as linhas cujo `Código da intimação`
está na lista extraída da aba Resumo.

### 5. `calcular_prioridade`
Critério de ordenação (validado com a solicitante):
1. `Data de disponibilização/evento` — mais próxima/urgente primeiro.
2. Situação do prazo — linhas com prazo em aberto vêm antes.

Como a maioria das linhas vem com `Prazo inicial`/`Prazo final` vazios, o
prazo real está embutido no texto de `Conteúdo`, no formato:
```
Data Intimação: 2026-08-22 23:59:59.999 Prazo: 15 dias úteis
```
Extraia via regex `Data Intimação:\s*([\d-]+)` e `Prazo:\s*(.+?)(?:$|\s{2,})`
como fallback quando as colunas estruturadas vierem vazias. Adicione uma
coluna auxiliar `Origem do prazo` (`"coluna"` ou `"texto"` ou `"não
encontrado"`) pra deixar rastreável.

"Prazo em aberto" = ainda não passou da data-limite (comparar com a data
de hoje). Linhas com prazo em aberto ficam no topo da ordenação.

### 6. `gerar_planilha_final`
Exportar pra `output/`, com:
- Fonte Arial, cabeçalho congelado (freeze panes), autofiltro ativado.
- Preenchimento colorido condicional (defina cores distintas e
  consistentes) para: linha com palavra-chave encontrada, processo
  repetido, conteúdo duplicado, teor incompleto. Uma linha pode acumular
  mais de um sinalizador — cuidado pra não sobrescrever cores, considere
  uma coluna de "sinalizadores" resumindo tudo, além das cores.
- Nunca sobrescrever o arquivo original em `input/`.

## Critérios de aceite

- Rodar `python src/main.py input/Doc-102_intimações_13-08-2026.xlsx` sem
  erro e gerar `output/Doc-102_intimações_13-08-2026_organizado.xlsx`.
- As 12 duplicidades de processo presentes nesse arquivo de exemplo devem
  aparecer corretamente marcadas e contadas.
- Os 2 itens de teor incompleto listados na aba Resumo desse arquivo devem
  ser marcados na saída.
- Testar com `config.PALAVRAS_CHAVE` vazia (não deve quebrar) e com
  algumas palavras de teste adicionadas manualmente.
