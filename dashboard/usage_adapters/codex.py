"""OpenAI Codex（ChatGPT 订阅，OAuth）适配器。

端点：GET https://chatgpt.com/backend-api/wham/usage （codex CLI 使用的半官方接口）
认证：读 ~/.codex/auth.json 的 OAuth access_token + account_id。
注意：access_token 会过期；codex CLI 运行时会自动刷新 auth.json。
     若返回 401，提示用户跑一次 `codex login` 或任意 codex 命令即可。
"""

import json
import os
import urllib.request
import urllib.error

from usage_adapters.base import UsageAdapter


class CodexAdapter(UsageAdapter):
    id = "openai-codex"
    name = "Codex (ChatGPT)"
    serves = ["openai-codex"]
    match = ["gpt"]

    def fetch(self) -> dict:
        auth_path = os.path.expanduser("~/.codex/auth.json")
        try:
            auth = json.load(open(auth_path))
            tokens = auth.get("tokens") or {}
            access = tokens.get("access_token", "")
            account = tokens.get("account_id", "")
        except (OSError, json.JSONDecodeError) as e:
            return self.fail("no_auth_file", f"无法读取 {auth_path}: {e}")
        if not access:
            return self.fail("no_token", "auth.json 中无 access_token")

        req = urllib.request.Request(
            "https://chatgpt.com/backend-api/wham/usage",
            headers={
                "Authorization": "Bearer " + access,
                "ChatGPT-Account-Id": account,
                "User-Agent": "codex-cli",
            })
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return self.fail("oauth_expired",
                                 "OAuth token 已过期，请运行一次 codex 命令刷新")
            return self.fail(f"http_{e.code}", e.read().decode()[:200])
        except Exception as e:
            return self.fail("network", f"{type(e).__name__}: {e}")

        rl = d.get("rate_limit") or {}
        windows = []
        for key, label in (("primary_window", "5小时"), ("secondary_window", "本周")):
            w = rl.get(key) or {}
            if w:
                windows.append({
                    "label": label,
                    "used_percent": w.get("used_percent"),
                    "used": None, "limit": None,
                    "reset_at": _ts_to_iso(w.get("reset_at")),
                })
        plan = d.get("plan_type")
        if not windows:
            return self.fail("parse", "响应中无 rate_limit 窗口")
        return self.ok(kind="quota", windows=windows,
                       plan=plan.capitalize() if plan else None)


def _ts_to_iso(ts):
    if not ts:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


ADAPTER = CodexAdapter()
