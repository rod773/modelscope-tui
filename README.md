# Modelscope TUI

A terminal AI coding assistant powered by [Modelscope](https://modelscope.ai) that can read, write, edit, delete, and list files — like opencode but **you choose the model**.

## How it was built

This project was created entirely through a conversation with an AI agent (opencode). The prompt used to generate it is in [`prompt.txt`](./prompt.txt).

### Architecture

```
modelscope-tui/
├── .env                      # user configuration (gitignored)
├── .env.example              # template for environment variables
├── main.py                   # entry point
├── pyproject.toml            # packaging and dependencies
├── requirements.txt          # pip dependencies
├── run.ps1                   # convenience launcher
├── prompt.txt                # the original build prompt
└── src/
    ├── __init__.py
    ├── config.py             # loads .env via python-dotenv (explicit path, override mode)
    ├── client.py             # httpx client for Modelscope API (handles 401, 404)
    ├── editor.py             # file tools + shell command execution + scaffolding
    ├── nextjs.py             # Next.js project scaffolding
    └── tui.py                # terminal UI with tool-calling loop + system prompt
```

**Data flow:**

```
You type a message
       ↓
  src/tui.py  ── API call ──→  Modelscope API (OpenAI-compatible)
       ↓                              ↓
  Tool call? ──────yes──────→  src/editor.py (file ops, shell commands, scaffolding)
       ↓                              ↓
  Tool result sent back ──→   AI processes result, may call more tools
       ↓
  Final response printed to terminal
```

## Requirements

- Python 3.10+
- A [Modelscope account](https://modelscope.ai) linked to Alibaba Cloud with real-name verification
- A Modelscope API token

## Setup

### 1. Get an API token

1. Go to **https://modelscope.ai/my-access-token**
2. Create a new token (choose "Long-term use")
3. Copy the token (it only shows once)

### 2. Configure

Copy the example env file and add your token:

```bash
cp .env.example .env
```

Edit `.env`:

```env
MODELSCOPE_API_TOKEN=ms-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MODELSCOPE_BASE_URL=https://api-inference.modelscope.ai/v1/
MODELSCOPE_MODEL=Qwen/Qwen2.5-72B-Instruct
WORKSPACE_DIR=.
```

| Variable | Purpose | Default |
|---|---|---|
| `MODELSCOPE_API_TOKEN` | Your API token (required) | — |
| `MODELSCOPE_BASE_URL` | API endpoint | `https://api-inference.modelscope.ai/v1/` |
| `MODELSCOPE_MODEL` | Model to use | `Qwen/Qwen2.5-72B-Instruct` |
| `WORKSPACE_DIR` | Working directory for file ops | `.` |

> For users in mainland China, use `.cn` instead of `.ai` in the base URL.

> **Note:** System environment variables do NOT override `.env` — the project always loads `.env` from its own directory with `override=True`. This ensures portable behavior across terminals.

### 3. Install

**Option A — Install as a command (recommended):**

```bash
pip install -e .
modelscope_tui
```

**Option B — Run directly:**

```bash
pip install -r requirements.txt
python main.py
```

## Usage

Once running, you chat with the AI just like any assistant. The AI has access to file tools and can create, read, edit, delete, and list files in your workspace.

### Commands

| Command | Description |
|---|---|
| `/help` | Show available commands |
| `/check` | Test API connection and show diagnostic info |
| `/clear` | Clear conversation history |
| `/model <name>` | Switch to a different model (e.g. `Qwen/Qwen3-32B`) |
| `/tools` | List available file tools |
| `/create-nextjs [name]` | Scaffold a Next.js 14 project with TypeScript + Tailwind (default: `my-app`) |
| `/workspace <dir>` | Change the working directory |
| `/exit` | Quit |

### Example session

```
You: create a file called hello.py that prints "hello world"

Assistant: I'll create that file for you.

Tool: write_file({'path': 'hello.py', 'content': 'print("hello world")'})

Done! Created hello.py.

You: read it back to me

Assistant: 

Tool: read_file({'path': 'hello.py'})

Contents of hello.py:
```python
print("hello world")
```

You: change it to say "hello modelscope" instead

Assistant:

Tool: edit_file({'path': 'hello.py', 'old_string': 'hello world', 'new_string': 'hello modelscope'})

Done! Updated hello.py.
```

## Project details

### `src/config.py`
Loads `.env` via `python-dotenv` using an explicit path relative to the file (`Path(__file__).resolve().parent.parent / ".env"`) with `override=True`, so `.env` always takes precedence over system environment variables. Provides typed getters for all configuration values. `get_base_url()` ensures the URL ends with `/v1/`. Validates that the API token starts with `ms-`.

### `src/client.py`
`ModelscopeClient` wraps the [OpenAI-compatible chat completions endpoint](https://api-inference.modelscope.ai/v1/chat/completions) using `httpx`. Includes `check_connection()` for diagnostics. Handles 401 errors (invalid token) and 404 errors (missing `/v1/` in base URL) with clear guidance.

### `src/editor.py`
`FileEditor` provides seven tools that the AI can call:

| Tool | Description |
|---|---|
| `read_file` | Read file contents |
| `write_file` | Create or overwrite a file |
| `edit_file` | Replace exact text (single occurrence) |
| `delete_file` | Delete a file or empty directory |
| `list_files` | List directory contents |
| `run_command` | Execute shell commands — uses `subprocess.Popen` with `stdin=DEVNULL`, merges stderr→stdout, **streams output line-by-line in real-time** via a daemon thread, enforces 120s timeout with a clear error message on hang |
| `create_nextjs_project` | Scaffold a Next.js 14 project with TypeScript + Tailwind |

Tools are defined as [OpenAI function calling](https://platform.openai.com/docs/guides/function-calling) schemas.

#### Command streaming
When `run_command` is called, each line of stdout/stderr is printed to the terminal as it arrives (via `console.print`), so the user sees progress in real-time instead of waiting for the command to finish. If a command prompts for interactive input, it receives EOF immediately and will either fail fast or time out with a helpful message after 120 seconds.

### `src/nextjs.py`
Scaffolds a Next.js 14 project with TypeScript and Tailwind CSS (App Router). Run `/create-nextjs my-app` to generate 10 files including `package.json`, `next.config.ts`, `tsconfig.json`, `app/layout.tsx`, `app/page.tsx`, and Tailwind/PostCSS config.

### `src/tui.py`
The terminal UI built with `prompt_toolkit` and `rich`. Implements a tool-calling loop: send user message → AI responds or calls tools → execute tools → feed results back to AI → repeat until AI gives a final response.

The system prompt (`SYSTEM_PROMPT` constant) includes critical rules that guide AI behavior:
- **Inspect before acting** — always check project files (`package.json`, etc.) before running commands
- **Avoid hangs** — always use `-y`/`--yes` flags since commands that prompt for input will time out
- **Shadcn UI** — check for `components.json` first and use `npx shadcn add` if already initialized

`FileEditor` is initialized with `print_fn=console.print` so command output streams to the terminal in real-time.

## License

MIT
