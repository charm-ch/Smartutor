"""运行时配置存储（服务端）：设置页保存的配置优先于环境变量。

存储位置：data/settings.json（服务器本地文件，API Key 不落前端）。
优先级：环境变量（.env）为默认值 → settings.json 运行时覆盖。
"""
import json
from pathlib import Path

from app.core.config import settings

_SETTINGS_FILE = Path(settings.kb_data_dir).parent / "settings.json"


class SettingsStore:
    """读写运行时配置 JSON 文件。"""

    def __init__(self, path: Path = _SETTINGS_FILE):
        self.path = path

    def load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, key: str, default=None):
        return self.load().get(key, default)


store = SettingsStore()


def effective_settings() -> dict:
    """合并后的生效配置：settings.json 覆盖环境变量。"""
    overrides = store.load()
    return {**settings.model_dump(), **overrides}


def mask_api_key(key: str) -> str:
    """脱敏：sk-****后4位。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:3]}****{key[-4:]}"
