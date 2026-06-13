"""本地配置读写服务。"""

import json
from pathlib import Path

from testdaf_platform.config import CONFIG_FILE


class ConfigStore:
    """管理保存在用户目录下的轻量配置。"""

    def __init__(self, path: Path = CONFIG_FILE):
        self.path = path

    def load_api_key(self) -> str:
        try:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as file:
                    cfg = json.load(file)
                return cfg.get("api_key", "")
        except Exception:
            return ""
        return ""

    def save_api_key(self, key: str) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as file:
                json.dump({"api_key": key}, file, ensure_ascii=False)
        except Exception:
            # 配置保存失败不应阻断核心出题或转写流程。
            return

