import json
from typing import Any
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from . import config
from .client import ModelscopeClient
from .editor import FileEditor
from .nextjs import create_nextjs_project

console = Console()
style = Style.from_dict({"prompt": "ansicyan bold"})


SYSTEM_PROMPT = """You are an AI coding assistant with access to these tools:

### File tools
- `read_file` — read file contents
- `write_file` — create/overwrite a file
- `edit_file` — replace exact text in a file (single match)
- `delete_file` — delete a file or empty directory
- `list_files` — list directory contents

### Project tools
- `create_nextjs_project` — scaffold a full Next.js 14 project with TypeScript + Tailwind (preferred over writing files manually)
- `run_command` — execute shell commands (e.g. npm install, yarn add, npx, git, etc.)

## Critical rules

### Always inspect the project first
Before running any commands, ALWAYS use `list_files` and/or `read_file` (e.g. on `package.json`) to understand the project's current state. Do not assume what is already installed or configured.

### Avoid hanging commands
Commands that prompt for interactive input will hang until a 120-second timeout kills them. Always use non-interactive flags:
- `-y` or `--yes` for installers (apt, npm, npx, pip, etc.)
- `-f` for force operations
- Never run bare `npx shadcn@latest`, `npx shadcn init`, or similar commands that require prompts. Check for existing configuration first.

### Shadcn UI specifically
If asked to add shadcn:
1. Check if `components.json` exists — if yes, shadcn is already initialized, use `npx shadcn add <component>` (not `init`).
2. Check `package.json` to see if shadcn dependencies are already installed.
3. Only run `npx shadcn init` if `components.json` does NOT exist, and append `-y` if the CLI supports it.

When asked to create a Next.js project, use `create_nextjs_project`. If the user says "inside this folder" or "in the current directory", use "." as the project_name. After scaffolding, use `run_command` to install dependencies.
Work in the user's workspace.

## Response format for multi-step tasks

When a task requires multiple steps, include a plan section in your response:

```
## Plan
- [x] Completed step
- [ ] Current step description
- [ ] Future step
```

Mark the current step with `[ ]` and completed steps with `[x]`.
Update the plan after each tool call so the user can see progress."""


def run() -> None:
    try:
        client = ModelscopeClient()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        console.print(f"\nGet a token at: [cyan]{config.MODELSCOPE_TOKEN_URL}[/cyan]")
        return

    editor = FileEditor(print_fn=console.print)
    history = FileHistory(".chat_history")
    session = PromptSession(history=history)

    console.print(Panel.fit("Modelscope TUI — AI Coding Assistant", style="bold cyan"))
    console.print(f"Model: {config.get_model()}")
    console.print(f"Workspace: {editor.workspace}")
    console.print("Type /help for commands, /exit to quit.\n")

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            prompt = session.prompt("\nYou: ", style=style)
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye!")
            break

        cmd = prompt.strip()

        if not cmd:
            continue

        if cmd == "/exit":
            console.print("Bye!")
            break

        if cmd == "/check":
            console.print("\n[bold]Connection check:[/bold]")
            console.print(client.check_connection())
            continue

        if cmd == "/help":
            console.print(Panel(
                "/exit    - quit\n"
                "/check   - test API connection\n"
                "/clear   - clear conversation\n"
                "/create-nextjs [name] - scaffold a Next.js project\n"
                "/model <name> - switch model\n"
                "/tools   - show available tools\n"
                "/workspace <dir> - change workspace\n"
                "Everything else is sent to the AI.",
                title="Commands",
            ))
            continue

        if cmd == "/clear":
            messages.clear()
            messages.append({"role": "system", "content": SYSTEM_PROMPT})
            console.print("[dim]Conversation cleared.[/dim]")
            continue

        if cmd == "/tools":
            for t in editor.get_tool_definitions():
                console.print(f"[bold cyan]{t['function']['name']}[/bold cyan]: {t['function']['description']}")
            continue

        if cmd.startswith("/model "):
            new_model = cmd[7:].strip()
            if new_model:
                import os
                os.environ["MODELSCOPE_MODEL"] = new_model
                client.model = new_model
                console.print(f"Switched to model: {new_model}")
            continue

        if cmd.startswith("/workspace "):
            new_ws = cmd[11:].strip()
            if new_ws:
                import os
                os.environ["WORKSPACE_DIR"] = new_ws
                editor.workspace = config.get_workspace()
                console.print(f"Workspace changed to: {editor.workspace}")
            continue

        if cmd.startswith("/create-nextjs"):
            parts = cmd.split(None, 1)
            name = parts[1].strip() if len(parts) > 1 else "my-app"
            try:
                dest = create_nextjs_project(editor.workspace, name)
                console.print(f"\n[bold green]Next.js project created at:[/bold green] {dest}")
                if name not in ("", "."):
                    console.print("\n[bold]To get started:[/bold]")
                    console.print(f"  cd {name}")
                    console.print("  npm install")
                    console.print("  npm run dev")
            except (FileExistsError, OSError) as e:
                console.print(f"\n[red]Error: {e}[/red]")
            continue

        messages.append({"role": "user", "content": cmd})

        while True:
            tool_call_cycle = len(messages) > 1 and any(m.get("role") == "tool" for m in messages[-3:])
            status_text = "Applying tool results..." if tool_call_cycle else "Thinking..."

            with console.status(status_text, spinner="dots"):
                try:
                    response = client.chat(messages, tools=editor.get_tool_definitions())
                except ValueError as e:
                    console.print(f"\n[red]{e}[/red]")
                    break
                except Exception as e:
                    console.print(f"\n[red]API error: {e}[/red]")
                    break

            choice = response["choices"][0]
            msg = choice["message"]

            reasoning = msg.get("reasoning_content", "") or ""
            if reasoning:
                console.print("\n[dim italic]Thinking:[/dim italic]")
                for line in reasoning.split("\n"):
                    console.print(f"[dim italic]{line}[/dim italic]")

            assistant_msg = {k: v for k, v in msg.items() if k != "reasoning_content"}

            tool_calls = assistant_msg.get("tool_calls")
            if not tool_calls:
                content = assistant_msg.get("content", "")
                if content:
                    console.print("\n[bold green]Assistant:[/bold green]")
                    console.print(Markdown(content))
                messages.append(assistant_msg)
                break

            msg_content = assistant_msg.get("content", "")
            if msg_content:
                console.print(Markdown(msg_content))

            messages.append(assistant_msg)

            for tc in tool_calls:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn["arguments"])
                except json.JSONDecodeError as e:
                    args = {}
                    console.print(f"[red]JSON parse error in tool args: {e}[/red]")

                console.print(f"\n[bold yellow]Tool:[/bold yellow] {name}({args})")

                try:
                    result = editor.execute_tool(name, args)
                    console.print(f"[dim]{result[:500]}[/dim]")
                except Exception as e:
                    result = f"Error: {e}"
                    console.print(f"[red]{result}[/red]")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
