# Model Usage — Hermes Plugin

[English](#english) | [中文](#中文)

---

## 中文

在 Hermes 桌面 App **状态栏**显示你当前所用模型的订阅/额度用量：5 小时窗口、本周窗口、余额，一目了然。点击弹出详情面板，查看所有已配置 provider 的全貌。

### 特性

- **状态栏跟随当前模型**：当前用哪个模型，就只显示哪个 provider 的用量（`5h 56% 周 26%` 或余额 `¥76`）
- **详情面板**：点击状态栏条目弹出，显示全部已配置 provider 的用量条、重置倒计时、计划类型
- **自动发现**：你在 Hermes 里正常添加 provider 后，插件自动扫描并纳入面板——无需重启、无需配置
- **开放适配器接口**：想支持新的 provider？往 `usage_adapters/` 目录丢一个几十行的 Python 文件即可
- **未适配占位**：没有公开用量接口的 provider（如 xAI）会以灰色折叠条提示"已配置但无用量接口"
- **密钥不出后端**：所有 API key 只由 Python 后端在本地持有，前端经 `ctx.rest` 拿数据，密钥永不进前端

### 已内置适配器

| Provider | 类型 | 数据来源 |
|---|---|---|
| Kimi Code（kimi-code） | 订阅配额 | `api.kimi.com/coding/v1/usages` |
| Codex / ChatGPT（openai-codex） | 订阅配额 | `chatgpt.com/backend-api/wham/usage`（本地 OAuth） |
| DeepSeek | 预付费余额 | `api.deepseek.com/user/balance` |
| Moonshot 开放平台（kimi-coding） | 预付费余额 | `api.moonshot.cn/v1/users/me/balance` |
| OpenRouter | 预付费额度 | `openrouter.ai/api/v1/credits` |

### 安装

```bash
hermes plugins install model-usage
```

或手动：把本仓库内容放到 `~/.hermes/plugins/model-usage/`，在 Settings → Plugins 启用。

### 添加新 provider 适配器

以 Grok 为例，新建 `dashboard/usage_adapters/xai.py`：

```python
from usage_adapters.base import UsageAdapter

class XAIAdapter(UsageAdapter):
    id = "xai"                    # 对应 Hermes provider id
    name = "xAI"
    serves = ["xai"]
    match = ["grok"]              # 模型名匹配子串（兜底，discovery 会自动补充）
    def fetch(self):
        key = self.env("XAI_API_KEY")
        if not key:
            return self.fail("no_api_key", "未设置 XAI_API_KEY")
        # ... 调接口，返回 self.quota(...) 或 self.balance_result(...)
```

重启 Hermes 后自动生效。详见各适配器源码（都有详细 docstring）。

### 隐私

本插件不收集、不上传任何数据。所有请求只发往对应 provider 官方接口。密钥仅从 `~/.hermes/.env`、Hermes 配置或本地 OAuth 文件读取。

---

## English

Shows **real-time subscription/quota usage for the model you're currently using** in the Hermes desktop status bar: 5-hour window, weekly window, or prepaid balance. Click for a full panel of all configured providers.

### Features

- **Follows your current model** — only shows the provider matching the active model (`5h 56% 周 26%` or balance)
- **Detail popover** — usage bars, reset countdowns, plan types for every configured provider
- **Auto-discovery** — add a provider to Hermes normally and it appears in the panel automatically
- **Open adapter interface** — drop a ~50-line Python file into `usage_adapters/` to support a new provider
- **Graceful fallback** — providers without a public usage API show as a collapsed "no usage API" section
- **Keys never leave the backend** — all credentials stay in the local Python backend; the frontend reads data via `ctx.rest`

### Bundled adapters

Kimi Code, Codex/ChatGPT (OAuth), DeepSeek, Moonshot Platform, OpenRouter.

### License

MIT
