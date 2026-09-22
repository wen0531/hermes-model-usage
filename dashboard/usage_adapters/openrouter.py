"""OpenRouter 适配器（预付费余额型）。

端点：GET https://openrouter.ai/api/v1/credits （官方文档接口）
认证：Bearer OPENROUTER_API_KEY
返回：total_credits / total_usage，差额即剩余额度。
"""

import json
import urllib.request
import urllib.error

from usage_adapters.base import UsageAdapter, get_env


class OpenRouterAdapter(UsageAdapter):
    id = "openrouter"
    name = "OpenRouter"
    serves = ["openrouter"]
    match = ["openrouter"]

    def fetch(self) -> dict:
        key = get_env("OPENROUTER_API_KEY")
        if not key:
            return self.fail("no_api_key", "未找到 OPENROUTER_API_KEY")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/credits",
            headers={"Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return self.fail(f"http_{e.code}", e.read().decode()[:200])
        except Exception as e:
            return self.fail("network", f"{type(e).__name__}: {e}")

        data = d.get("data") or {}
        total = data.get("total_credits")
        used = data.get("total_usage")
        if total is None or used is None:
            return self.fail("parse", "响应中未找到 credits 字段")
        remaining = float(total) - float(used)
        return self.ok(kind="balance",
                       balance={"amount": f"{remaining:.2f}", "currency": "USD"},
                       detail=f"总充值 ${total}，已用 ${used}")


ADAPTER = OpenRouterAdapter()
