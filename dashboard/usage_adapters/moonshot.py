"""Moonshot 开放平台适配器（按量计费，余额型）。

端点：GET https://api.moonshot.cn/v1/users/me/balance （官方文档接口）
认证：Bearer KIMI_API_KEY / MOONSHOT_API_KEY
返回：available_balance / voucher_balance / cash_balance。
注意：这是开放平台（platform.moonshot.cn）的余额，不是 Kimi Code 订阅
（订阅走 kimi_code.py 的 /coding/v1/usages）。
"""

import json
import urllib.request
import urllib.error

from usage_adapters.base import UsageAdapter, get_env


class MoonshotAdapter(UsageAdapter):
    id = "moonshot"
    name = "Moonshot 开放平台"
    serves = ["moonshot"]
    match = ["moonshot"]

    def fetch(self) -> dict:
        key = get_env("MOONSHOT_API_KEY") or get_env("KIMI_API_KEY")
        if not key:
            return self.fail("no_api_key", "未找到 MOONSHOT_API_KEY / KIMI_API_KEY")
        req = urllib.request.Request(
            "https://api.moonshot.cn/v1/users/me/balance",
            headers={"Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return self.fail(f"http_{e.code}", e.read().decode()[:200])
        except Exception as e:
            return self.fail("network", f"{type(e).__name__}: {e}")

        data = d.get("data") or {}
        available = data.get("available_balance")
        if available is None:
            return self.fail("parse", "响应中未找到 available_balance")
        return self.ok(kind="balance",
                       balance={"amount": f"{float(available):.2f}", "currency": "CNY"},
                       detail=f"现金 ¥{data.get('cash_balance', '?')} + 代金券 ¥{data.get('voucher_balance', '?')}")


ADAPTER = MoonshotAdapter()
