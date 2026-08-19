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

1. **Palavras-chave com peso** — busca no texto da coluna `Conteúdo` (teor
   da intimação) e sinaliza as linhas que contêm termos relevantes. Cada
   termo tem um peso (ver `src/config.py`), usado como desempate na
   ordenação.
2. **Ordem de importância** — ordena diretamente pela data-limite do prazo
   (da coluna estruturada ou extraída do texto de `Conteúdo`), do prazo mais
   próximo de vencer para o mais distante; linhas sem data-limite
   identificada ficam no final. Entre linhas com prazo igual, o peso das
   palavras-chave desempata. Além disso, **agrupa as intimações do mesmo
   processo**: o grupo aparece na posição da sua intimação mais urgente, e
   as demais do mesmo processo ficam logo em seguida.
3. **Processos repetidos** — sinaliza quando o mesmo `Nº do processo`
   aparece mais de uma vez no dia, com contagem de repetições. Também
   sinaliza quando o *conteúdo* do texto se repete entre linhas, mesmo que o
   processo seja diferente.
4. **Itens com teor incompleto** — a aba `Resumo` às vezes lista códigos de
   intimação que o sistema não conseguiu exportar por completo. Essas linhas
   são marcadas separadamente na saída, pra não passarem batido.

Na interface web, além da planilha exportável, dá pra fazer a triagem direto
na tela (`/intimacoes`) — ver a fila de intimações pendentes e marcar cada
uma como tratada, sem precisar reabrir o Excel.

## Escopo confirmado com a solicitante (13/08/2026)

- Palavras-chave: lista inicial a definir em reunião (ver `src/config.py`),
  cada termo com um peso.
- Critério de prioridade: data-limite do prazo manda (mais próxima de vencer
  primeiro); peso da palavra-chave só desempata. Intimações do mesmo
  processo ficam agrupadas, na posição da mais urgente do grupo.
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
│   ├── intimacoes_db.py   # banco local das intimações processadas (SQLite) — fila de tratamento
│   ├── webapp.py          # interface web (FastAPI)
│   ├── usuarios.db        # gerado ao criar o 1º usuário — nunca versionado
│   ├── intimacoes.db      # gerado no 1º upload — nunca versionado
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

Se alguém esquecer a senha, o admin clica em **"Redefinir senha"** ao lado
do usuário em `/admin/usuarios` — gera uma senha temporária aleatória,
mostrada uma única vez na tela pra ser repassada com segurança (não
precisa saber a senha antiga).

### 2. Rodar o servidor

A partir da raiz do projeto:

```bash
uvicorn src.webapp:app --reload
```

Acesse `http://localhost:8000` — vai redirecionar para `/login`. Entre com
o usuário criado no passo 1, envie o `.xlsx` bruto e baixe a planilha
organizada, com um resumo (linhas, processos repetidos, itens com teor
incompleto) na mesma página.

### Tratar intimações direto na tela (sem baixar planilha)

Depois de processar um arquivo, clique em **"Tratar intimações na tela"**
(ou acesse `/intimacoes` a qualquer momento pelo link **"Intimações"** no
topo) pra ver a fila de triagem: todas as intimações já processadas em
qualquer upload, ordenadas pelo prazo mais próximo de vencer, com as mesmas
cores/sinalizadores da planilha.

- Clique em **"Marcar tratada"** numa linha — ela some da aba "Pendentes" e
  passa a aparecer em "Tratadas" (com quem tratou e quando), com um botão
  pra desmarcar caso seja engano.
- Buscar filtra por processo, termo de pesquisa ou conteúdo.
- Reenviar o mesmo arquivo (ou um novo com intimações repetidas) não duplica
  nada — a identidade de cada intimação é o "Código da intimação" (único no
  Publicações Online), então reprocessar só atualiza os dados sem mexer no
  que já foi marcado como tratado.
- Qualquer usuário logado (admin ou comum) pode usar essa tela.
- Um aviso amarelo aparece no topo da Triagem e da tela de Intimações
  sempre que houver pendentes com prazo vencido ou vencendo nos próximos
  dias (`config.DIAS_ALERTA_PRAZO`, padrão 3) — pra não depender de alguém
  lembrar de checar.

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
