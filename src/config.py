import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()


# Use .ai for international users, .cn for mainland China
MODELSCOPE_TOKEN_URL = "https://modelscope.ai/my-access-token"


def get_api_token() -> str:
    token = os.getenv("MODELSCOPE_API_TOKEN")
    if not token:
        raise ValueError(
            f"MODELSCOPE_API_TOKEN not set.\n"
            f"Get a token at {MODELSCOPE_TOKEN_URL} and add it to your .env file:\n"
            f"MODELSCOPE_API_TOKEN=ms-xxxxxxxxxxxx"
        )
    if not token.startswith("ms-"):
        raise ValueError(
            f"MODELSCOPE_API_TOKEN looks invalid (should start with 'ms-').\n"
            f"Get a valid token at {MODELSCOPE_TOKEN_URL}"
        )
    return token


def get_base_url() -> str:
    return os.getenv(
        "MODELSCOPE_BASE_URL",
        "https://api-inference.modelscope.ai/v1/",
    ).rstrip("/") + "/"


def get_model() -> str:
    return os.getenv("MODELSCOPE_MODEL", "Qwen/Qwen2.5-72B-Instruct")


def get_workspace() -> Path:
    return Path(os.getenv("WORKSPACE_DIR", ".")).resolve()
