import json
from typing import Any
import httpx
from . import config


class ModelscopeClient:
    def __init__(self):
        self.token = config.get_api_token()
        self.base_url = config.get_base_url()
        self.model = config.get_model()
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )

    def check_connection(self) -> str:
        info = (
            f"Token: {self.token[:12]}...{self.token[-4:]}\n"
            f"Base URL: {self.base_url}\n"
            f"Model: {self.model}\n"
        )
        try:
            resp = self._http.post("chat/completions", json={
                "model": self.model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            })
            info += f"Status: {resp.status_code}\n"
            info += f"Response: {resp.text[:500]}"
        except Exception as e:
            info += f"Error: {e}"
        return info

    def chat(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            body["tools"] = tools

        resp = self._http.post("chat/completions", json=body)
        if resp.status_code == 401:
            detail = resp.text[:500]
            raise ValueError(
                f"401 Unauthorized. Token is invalid or account needs setup.\n"
                f"API response: {detail}\n"
                f"Get a new token at: {config.MODELSCOPE_TOKEN_URL}"
            )
        if resp.status_code == 404:
            raise ValueError(
                f"404 Not Found. Check that MODELSCOPE_BASE_URL includes /v1/.\n"
                f"Current base URL: {self.base_url}\n"
                f"Full URL: {resp.url}"
            )
        if resp.status_code == 405:
            raise ValueError(
                f"405 Method Not Allowed. The API endpoint may have changed or your message "
                f"content may be too long.\n"
                f"Current base URL: {self.base_url}\n"
                f"Full URL: {resp.url}"
            )
        resp.raise_for_status()
        return resp.json()

    def chat_stream(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None = None):
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            body["tools"] = tools

        with self._http.stream("POST", "chat/completions", json=body) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data and data != "[DONE]":
                        import json
                        yield json.loads(data)
