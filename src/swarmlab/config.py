from dataclasses import dataclass, field
from pathlib import Path
import os
import re

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    host: str = ""
    port: int = 6379
    username: str = "falkordb"
    password: str = field(default="", repr=False)
    tls: bool = True
    graph: str = "swarmlab_demo"
    model_provider: str = ""
    model_name: str = ""
    model_api_key: str = field(default="", repr=False)

    @classmethod
    def load(cls, env_file: Path | None = None):
        values = {**dotenv_values(env_file or ROOT / ".env"), **os.environ}
        def get(key, default=""):
            return values.get(key) or default
        tls = get("FALKORDB_TLS", "true").lower()
        if tls not in {"true", "false"}:
            raise ValueError("FALKORDB_TLS must be true or false")
        graph = get("FALKORDB_GRAPH", "swarmlab_demo")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", graph):
            raise ValueError("FALKORDB_GRAPH must be a simple application graph name")
        port = int(get("FALKORDB_PORT", "6379"))
        if not 1 <= port <= 65535:
            raise ValueError("FALKORDB_PORT must be between 1 and 65535")
        provider = get("MODEL_PROVIDER", "gemini").strip()
        return cls(
            host=get("FALKORDB_HOST").strip(), port=port,
            username=values.get("FALKORDB_USERNAME", "") or "",
            password=get("FALKORDB_PASSWORD"), tls=tls == "true", graph=graph,
            model_provider=provider,
            model_name=get("MODEL_NAME", "gemini-3.5-flash-lite" if provider == "gemini" else "gpt-6.1-sol").strip(),
            model_api_key=get("GEMINI_API_KEY") if provider == "gemini" else get("MODEL_API_KEY"),
        )

    def public_status(self):
        return {
            "database_host_configured": bool(self.host),
            "database_password_configured": bool(self.password),
            "database_local": self.host in {"localhost", "127.0.0.1", "::1"},
            "database_tls": self.tls,
            "graph": self.graph,
            "model_provider": self.model_provider or None,
            "model_name": self.model_name or None,
            "model_key_configured": bool(self.model_api_key),
        }
