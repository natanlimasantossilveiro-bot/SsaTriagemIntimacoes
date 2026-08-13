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
2. **Ordem de importância** — ordena diretamente pela data-limite do prazo
   (da coluna estruturada ou extraída do texto de `Conteúdo`), do prazo mais
   próximo de vencer para o mais distante. Linhas sem data-limite
   identificada ficam no final.
3. **Processos repetidos** — sinaliza quando o mesmo `Nº do processo`
   aparece mais de uma vez no dia, com contagem de repetições. Também
   sinaliza quando o *conteúdo* do texto se repete entre linhas, mesmo que o
   processo seja diferente.
4. **Itens com teor incompleto** — a aba `Resumo` às vezes lista códigos de
   intimação que o sistema não conseguiu exportar por completo. Essas linhas
   são marcadas separadamente na saída, pra não passarem batido.

## Escopo confirmado com a solicitante (13/08/2026)

- Palavras-chave: lista inicial a definir em reunião (ver `src/config.py`).
- Critério de prioridade: data-limite do prazo (mais próxima de vencer primeiro).
- Busca de palavra-chave: apenas no texto da coluna `Conteúdo`.
- Repetição: marcar linha + coluna com quantidade de repetições; sinalizar
  também repetição de conteúdo.
- Sem SharePoint por enquanto — output local, pasta da controladoria futura.

## Estrutura

```
SsaTriagemIntimacoes/
├── input/               # coloque aqui o .xlsx bruto extraído do Publicações Online
├── output/               # planilha organizada é gerada aqui
├── src/
│   ├── config.py          # lista de palavras-chave e parâmetros ajustáveis
│   ├── main.py            # pipeline de processamento + CLI
│   ├── usuarios_db.py     # banco local de usuários do webapp (SQLite + bcrypt)
│   ├── manage_users.py    # CLI de administração de usuários (criar/listar/remover)
│   ├── webapp.py          # interface web (FastAPI)
│   ├── usuarios.db        # gerado ao criar o 1º usuário — nunca versionado
│   └── templates/         # páginas HTML (Jinja2) do webapp
├── tests/
├── Dockerfile
└── requirements.txt
```

## Uso via linha de comando

```bash
pip install -r requirements.txt
python src/main.py input/NOME_DO_ARQUIVO.xlsx
```

Gera `output/NOME_DO_ARQUIVO_organizado.xlsx`.

## Uso via interface web

A interface web reaproveita o mesmo pipeline do CLI — o resultado do
processamento é idêntico, só muda a forma de enviar o arquivo e baixar o
resultado. Não existe cadastro público: usuários só existem se um admin
criar (via CLI ou pela própria interface web).

Existem dois perfis: **admin** (acessa `/admin/usuarios` — cria e remove
outros usuários) e **usuário comum** (só usa a triagem). O primeiro usuário
criado no banco vira admin automaticamente.

### 1. Criar o primeiro usuário (vira admin automaticamente)

```bash
python src/manage_users.py criar admin
```

A senha é pedida via prompt (sem eco no terminal). Outros comandos:

```bash
python src/manage_users.py listar               # mostra usuário e perfil (admin / usuário comum)
python src/manage_users.py criar outro --admin   # força --admin manualmente (além do 1º usuário, que já vira admin sozinho)
python src/manage_users.py remover admin
```

Os usuários ficam em `src/usuarios.db` (SQLite local, senhas com hash
bcrypt via passlib) — esse arquivo nunca é versionado.

A partir do segundo usuário em diante, o mais prático é criar direto pela
interface web: logado como admin, use o link **"Gerenciar usuários"** no
topo da página (leva a `/admin/usuarios`) — cria e remove usuários sem
precisar de terminal. Usuários comuns não veem esse link e recebem 403 se
tentarem acessar a rota diretamente.

### 2. Rodar o servidor

A partir da raiz do projeto:

```bash
uvicorn src.webapp:app --reload
```

Acesse `http://localhost:8000` — vai redirecionar para `/login`. Entre com
o usuário criado no passo 1, envie o `.xlsx` bruto e baixe a planilha
organizada, com um resumo (linhas, processos repetidos, itens com teor
incompleto) na mesma página.

Defina a variável de ambiente `SSA_SECRET_KEY` antes de rodar em qualquer
ambiente exposto (a chave assina o cookie de sessão). Sem ela, o webapp usa
uma chave de desenvolvimento fixa e avisa no console:

```bash
export SSA_SECRET_KEY="uma-chave-aleatoria-longa"   # Linux/Mac
$env:SSA_SECRET_KEY = "uma-chave-aleatoria-longa"    # PowerShell
```

### 3. Expor via Ngrok (teste temporário)

Com o servidor rodando na porta 8000:

```bash
ngrok http 8000
```

O Ngrok gera uma URL pública temporária apontando pro seu `localhost:8000`
— use essa URL pra a solicitante testar pelo navegador. Quando for pra VPS,
o `Dockerfile` na raiz já está pronto (`docker build` + `docker run`,
expondo a porta 8000).
