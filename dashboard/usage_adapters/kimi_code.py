"""Kimi Code（kimi-for-coding 订阅）适配器。

端点：GET https://api.kimi.com/coding/v1/usages （社区确认，官方文档未列）
认证：Bearer KIMI_CODE_API_KEY（Kimi Code 控制台的 sk-kimi-* key）
返回：5小时窗 + 7天窗的 used_ratio / reset_time，及请求计数。
"""

import json
import urllib.request
import urllib.error

from usage_adapters.base import UsageAdapter, get_env


class KimiCodeAdapter(UsageAdapter):
    id = "kimi-code"
    name = "Kimi Code"
    serves = ["kimi-code", "kimi-coding", "kimi-coding-cn"]
    match = ["k3", "kimi"]

    def fetch(self) -> dict:
        key = get_env("KIMI_CODE_API_KEY")
        if not key:
            return self.fail("no_api_key", "未找到 KIMI_CODE_API_KEY")
        req = urllib.request.Request(
            "https://api.kimi.com/coding/v1/usages",
            headers={"Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return self.fail(f"http_{e.code}", e.read().decode()[:200])
        except Exception as e:
            return self.fail("network", f"{type(e).__name__}: {e}")

        windows = []
        usages = d.get("usages") or {}
        counts = d.get("usage") or {}
        limits = d.get("limits") or []

        w5 = usages.get("limit_5h") or {}
        det5 = (limits[0].get("detail") if limits else {}) or {}
        if w5:
            windows.append({
                "label": "5小时",
                "used_percent": round((w5.get("used_ratio") or 0) * 100),
                "used": det5.get("used"), "limit": det5.get("limit"),
                "reset_at": w5.get("reset_time"),
            })
        w7 = usages.get("limit_7d") or {}
        if w7:
            windows.append({
                "label": "本周",
                "used_percent": round((w7.get("used_ratio") or 0) * 100),
                "used": counts.get("used"), "limit": counts.get("limit"),
                "reset_at": w7.get("reset_time"),
            })
        if not windows:
            return self.fail("parse", "响应中未找到用量窗口")
        return self.ok(kind="quota", windows=windows)


ADAPTER = KimiCodeAdapter()
