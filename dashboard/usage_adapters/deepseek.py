"""DeepSeek 适配器（按量计费，余额型）。

端点：GET {DEEPSEEK_BASE_URL}/user/balance （官方文档接口）
认证：Bearer DEEPSEEK_API_KEY
"""

import json
import urllib.request
import urllib.error

from usage_adapters.base import UsageAdapter, get_env


class DeepSeekAdapter(UsageAdapter):
    id = "deepseek"
    name = "DeepSeek"
    serves = ["deepseek"]
    match = ["deepseek"]

    def fetch(self) -> dict:
        key = get_env("DEEPSEEK_API_KEY")
        if not key:
            return self.fail("no_api_key", "未找到 DEEPSEEK_API_KEY")
        base = get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        req = urllib.request.Request(base + "/user/balance",
                                     headers={"Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return self.fail(f"http_{e.code}", e.read().decode()[:200])
        except Exception as e:
            return self.fail("network", f"{type(e).__name__}: {e}")

        infos = d.get("balance_infos") or []
        if not infos:
            return self.fail("parse", "响应中无 balance_infos")
        b = infos[0]
        return self.ok(kind="balance", balance={
            "amount": b.get("total_balance", "?"),
            "currency": b.get("currency", "CNY"),
        })


ADAPTER = DeepSeekAdapter()
