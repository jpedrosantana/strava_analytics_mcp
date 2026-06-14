# Quickstart — começando do zero

Guia passo a passo para rodar o projeto **mesmo sem experiência com programação**.
Você não precisa saber programar — vai copiar e colar alguns comandos numa janela de
"terminal". Reserve uns **30–40 minutos** na primeira vez.

> **O que é isto, em uma frase:** uma ferramenta que roda **no seu computador**, baixa
> seu histórico do Strava para um banco local e calcula métricas de treino. Nada é
> enviado para a internet além das chamadas à própria API do Strava.

> **Travou em algum passo?** Veja o [Troubleshooting](TROUBLESHOOTING.md) ou abra uma
> issue. Para o passo a passo "de desenvolvedor" (mais enxuto), veja o [README](../README.md).

---

## Antes de começar, você vai precisar de

- Um computador com **Windows, macOS ou Linux**.
- Uma **conta no Strava** (a mesma que você usa para registrar os treinos).
- *(Opcional — só para "conversar" com seus dados)* o app **Claude Desktop**.

Nenhum conhecimento prévio de Python, git ou banco de dados é necessário.

---

## Passo 1 — Abrir o terminal

O "terminal" é uma janela onde você digita comandos.

- **Windows:** menu Iniciar → procure por **PowerShell** → abra.
- **macOS:** `Cmd + Espaço` → digite **Terminal** → Enter.
- **Linux:** `Ctrl + Alt + T` (ou procure por "Terminal").

Deixe essa janela aberta — todos os comandos abaixo são digitados (ou colados) nela.
Para colar: `Ctrl + V` (Windows/Linux) ou `Cmd + V` (Mac). Cada comando roda ao
apertar **Enter**.

---

## Passo 2 — Instalar o `uv` (e o Python)

O `uv` é a ferramenta que prepara e roda o projeto. Ele também instala a versão certa
do Python para você.

**Windows** (no PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Depois **feche e reabra o terminal** (para ele reconhecer o `uv`) e confirme que
funcionou:
```bash
uv --version
```
Se aparecer um número de versão, deu certo. Em seguida, instale o Python:
```bash
uv python install 3.11
```

---

## Passo 3 — Baixar o projeto

Você tem duas opções — escolha a que achar mais simples:

**Opção A (mais fácil, sem git):** baixe o `.zip` do projeto pelo botão verde
**Code → Download ZIP** na página do repositório no GitHub, e extraia numa pasta.

**Opção B (com git):**
```bash
git clone https://github.com/jpedrosantana/strava_analytics_mcp
```

Depois, **entre na pasta do projeto** no terminal:
```bash
cd strava_analytics_mcp
```
> Dica: digite `cd ` (com espaço) e arraste a pasta para dentro do terminal — ele
> preenche o caminho sozinho.

---

## Passo 4 — Criar seu app na Strava (pegar as chaves de acesso)

Para o projeto ler seus dados, a Strava exige que você crie um "app" e gere duas
chaves: **Client ID** e **Client Secret**.

1. Acesse **<https://www.strava.com/settings/api>** (logado na sua conta).
2. Preencha o formulário:
   - **Application Name:** qualquer nome (ex.: `Minhas Análises`).
   - **Category:** `Data Importer` (ou o que fizer sentido).
   - **Club:** deixe em branco.
   - **Website:** qualquer endereço (ex.: `http://localhost`).
   - **Authorization Callback Domain:** digite **`localhost`** (importante!).
3. Aceite os termos e clique em **Create**.
4. Na tela seguinte, copie o **Client ID** e o **Client Secret** — você vai usá-los no
   próximo passo.

> Quer ver o processo com mais detalhes? A
> [documentação oficial da Strava](https://developers.strava.com/docs/getting-started/)
> descreve a criação do app.

> O **Client Secret** é uma senha — não compartilhe nem coloque em prints públicos.

---

## Passo 5 — Configurar as chaves no projeto

Na pasta do projeto há um arquivo de exemplo chamado `.env.example`. Faça uma cópia
dele chamada `.env`:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```
**macOS / Linux:**
```bash
cp .env.example .env
```

Abra o arquivo `.env` num editor de texto simples (Bloco de Notas, TextEdit, etc.) e
cole suas chaves nas duas primeiras linhas:
```
STRAVA_CLIENT_ID=cole_seu_client_id_aqui
STRAVA_CLIENT_SECRET=cole_seu_client_secret_aqui
```
Salve e feche.

---

## Passo 6 — Instalar e autenticar

De volta ao terminal (dentro da pasta do projeto), prepare o projeto:
```bash
uv sync
```

Autentique com a Strava (abre o navegador para você autorizar — clique em **Authorize**):
```bash
uv run strava-mcp setup
```

Baixe **todo** o seu histórico + os dados detalhados (FC, pace, altitude) e calcule as
métricas. Esta etapa pode levar alguns minutos, dependendo de quantas atividades você tem:
```bash
uv run strava-mcp sync --full --streams --compute
```

Confira se está tudo certo:
```bash
uv run strava-mcp doctor
```

---

## Passo 7 — (recomendado) Configurar seus parâmetros

Algumas métricas ficam mais precisas com seus números fisiológicos (frequência cardíaca
máxima, limiar, ritmo de threshold). Abra
[`scripts/seed_athlete_config.py`](../scripts/seed_athlete_config.py), ajuste os valores
no topo do arquivo para os **seus**, salve, e rode:
```bash
uv run python scripts/seed_athlete_config.py
uv run strava-mcp compute-metrics
```
> Não sabe seus números ainda? Pode pular — o projeto estima FCmáx e limiar a partir do
> seu histórico. (O ritmo de threshold não é estimado; sem ele, a métrica `r_tss` fica vazia.)

---

## Passo 8 — Testar! Abrir o dashboard

Esta é a forma mais simples de ver seus dados funcionando — abre um painel visual no
navegador, sem precisar de mais nada:
```bash
./scripts/transform.sh    # organiza os dados (rode uma vez)
./scripts/dashboard.sh    # abre o painel no navegador
```
O terminal vai mostrar um endereço (algo como `http://localhost:8501`). Abra-o no
navegador e explore as páginas: forma atual, carga, eficiência, provas, rotas e mais.

Para encerrar o painel, volte ao terminal e aperte `Ctrl + C`.

---

## Passo 9 — (opcional) Conversar com seus dados via Claude

Se quiser fazer perguntas em linguagem natural ("qual minha forma atual?", "projete meu
tempo de maratona"), conecte o projeto ao **Claude Desktop**:

1. Instale o **Claude Desktop** (macOS ou Windows).
2. Abra o arquivo de configuração do Claude Desktop:
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
3. Cole o bloco abaixo (troque o caminho pelo caminho **absoluto** da pasta do projeto
   no seu computador):
   ```json
   {
     "mcpServers": {
       "strava-analytics": {
         "command": "uv",
         "args": ["run", "strava-mcp", "serve"],
         "cwd": "/caminho/absoluto/para/strava_analytics_mcp"
       }
     }
   }
   ```
4. Reinicie o Claude Desktop. Agora você pode pedir análises direto na conversa.

> **No Linux** (sem Claude Desktop) ou usando **Claude Code**, veja a seção
> [Integração com Claude Code](../README.md#integração-com-claude-code) do README.

---

## Deu algum erro?

- Comando "não encontrado" logo após instalar o `uv`? Feche e reabra o terminal.
- Problemas de login, limite da Strava, sync interrompido: veja o
  [Troubleshooting](TROUBLESHOOTING.md).
- Em último caso, apague a pasta `data/` e refaça o Passo 6 do zero.
