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

console = Console()
style = Style.from_dict({"prompt": "ansicyan bold"})


SYSTEM_PROMPT = """You are an AI coding assistant. You have access to file tools:
- `read_file` — read file contents
- `write_file` — create/overwrite a file
- `edit_file` — replace exact text in a file (single match)
- `delete_file` — delete a file or empty directory
- `list_files` — list directory contents

When asked to create or modify code, use the appropriate tool.
Explain what you are doing before executing tools.
Work in the user's workspace."""


def run() -> None:
    try:
        client = ModelscopeClient()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        console.print(f"\nGet a token at: [cyan]{config.MODELSCOPE_TOKEN_URL}[/cyan]")
        return

    editor = FileEditor()
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
