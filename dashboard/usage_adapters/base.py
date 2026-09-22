"""适配器基类与标准化输出 schema。

新增 provider = 在 adapters/ 目录丢一个 .py 文件，定义一个 ADAPTER 实例即可。
插件启动时自动扫描注册，无需改其他任何文件。

标准化输出 schema（fetch() 返回值）：
{
  "id":       str,            # provider 唯一标识
  "name":     str,            # 显示名
  "ok":       bool,           # 本次是否成功
  "kind":     "quota"|"balance"|"mixed",  # 数据形态
  "windows":  [               # 配额窗口（5小时/周/月…），可多个；无则为 []
    {"label": str,            # "5小时" / "本周" …
     "used_percent": int,     # 0-100
     "used": str|None,        # 原始计数（如 "23/100 次"），没有则 None
     "limit": str|None,
     "reset_at": str|None}    # ISO 时间，配额重置时刻
  ],
  "balance":  {"amount": str, "currency": str} | None,   # 余额型
  "plan":     str|None,       # 订阅档位名（如 "Plus" / "Allegretto"）
  "expiry":   str|None,       # 订阅到期日 ISO；多数接口不提供，留 None
  "error":    str|None,       # ok=False 时的机器可读错误码
  "detail":   str|None,       # 人类可读补充说明
  "fetched_at": str           # ISO，本次抓取时间（由框架填充）
}
"""

import os
from datetime import datetime, timezone


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_env(key: str, default: str = "") -> str:
    """先读进程环境变量，再兜底解析 ~/.hermes/.env（gateway 不保证注入全部变量）。"""
    v = os.environ.get(key)
    if v:
        return v
    env_path = os.path.expanduser("~/.hermes/.env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, val = line.split("=", 1)
                    if k.strip() == key:
                        return val.strip().strip('"').strip("'")
    except OSError:
        pass
    return default


class UsageAdapter:
    """所有 provider 适配器的基类。子类必须设置 id/name 并实现 fetch()。"""

    id: str = "base"
    name: str = "Base"
    # 本适配器服务的 Hermes provider id（discovery 靠它把适配器和已配置 provider 对上）。
    # 多数情况下与 id 相同；一个适配器服务多个 provider 时列多个。
    serves: list = []
    # 模型名匹配子串（小写）：前端用它把"当前模型"映射到本 provider。
    # discovery 会自动把配置里该 provider 的模型名合并进来，这里只留兜底。
    # 例：["k3", "kimi"] 命中 "k3-256k"、"kimi-k2" 等模型名。
    match: list = []

    def fetch(self) -> dict:
        raise NotImplementedError

    # ---- 输出构造助手 ----
    def ok(self, kind="quota", windows=None, balance=None, plan=None,
           expiry=None, detail=None) -> dict:
        return {
            "id": self.id, "name": self.name, "ok": True, "kind": kind,
            "match": list(self.match),
            "windows": windows or [], "balance": balance, "plan": plan,
            "expiry": expiry, "error": None, "detail": detail,
        }

    def fail(self, error: str, detail: str = None) -> dict:
        return {
            "id": self.id, "name": self.name, "ok": False, "kind": "quota",
            "match": list(self.match),
            "windows": [], "balance": None, "plan": None,
            "expiry": None, "error": error, "detail": detail,
        }
