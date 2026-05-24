import os
from pathlib import Path
from . import config


class FileEditor:
    def __init__(self):
        self.workspace = config.get_workspace()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        return p.resolve()

    def read_file(self, path: str) -> str:
        full = self._resolve(path)
        if not full.exists():
            raise FileNotFoundError(f"File not found: {full}")
        return full.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {full}"

    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        full = self._resolve(path)
        if not full.exists():
            raise FileNotFoundError(f"File not found: {full}")
        content = full.read_text(encoding="utf-8")
        if old_string not in content:
            raise ValueError(f"old_string not found in {full}")
        if content.count(old_string) > 1:
            raise ValueError(f"Found multiple matches for old_string in {full}. Provide more context.")
        new_content = content.replace(old_string, new_string)
        full.write_text(new_content, encoding="utf-8")
        return f"Edited {full}"

    def delete_file(self, path: str) -> str:
        full = self._resolve(path)
        if not full.exists():
            raise FileNotFoundError(f"File not found: {full}")
        if full.is_dir():
            full.rmdir()
            return f"Deleted directory: {full}"
        full.unlink()
        return f"Deleted file: {full}"

    def list_files(self, path: str = ".") -> str:
        full = self._resolve(path)
        if not full.exists() or not full.is_dir():
            raise NotADirectoryError(f"Not a directory: {full}")
        lines = []
        for entry in sorted(full.iterdir()):
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")
        return "\n".join(lines)

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative or absolute file path"}
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create a new file or overwrite an existing one",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative or absolute file path"},
                            "content": {"type": "string", "description": "Full file content"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Replace exact text in an existing file (single occurrence)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative or absolute file path"},
                            "old_string": {"type": "string", "description": "Text to replace"},
                            "new_string": {"type": "string", "description": "Replacement text"},
                        },
                        "required": ["path", "old_string", "new_string"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_file",
                    "description": "Delete a file or empty directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative or absolute file path"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files and directories in a folder",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Directory path, defaults to ."},
                        },
                    },
                },
            },
        ]

    def execute_tool(self, name: str, args: dict) -> str:
        match name:
            case "read_file":
                return self.read_file(args["path"])
            case "write_file":
                return self.write_file(args["path"], args["content"])
            case "edit_file":
                return self.edit_file(args["path"], args["old_string"], args["new_string"])
            case "delete_file":
                return self.delete_file(args["path"])
            case "list_files":
                return self.list_files(args.get("path", "."))
            case _:
                raise ValueError(f"Unknown tool: {name}")
