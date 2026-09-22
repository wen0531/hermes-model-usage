"""Provider 自动发现：扫 Hermes 配置，找出用户实际配置过哪些 provider。

数据源（按可靠性排序）：
1. config.yaml 的 providers: 字典（custom provider，如 kimi-code）
2. Hermes 内置 PROVIDER_REGISTRY 中、环境变量里存在对应 key 的（如 deepseek）
3. OAuth 型：本地凭证文件存在（目前支持 openai-codex -> ~/.codex/auth.json）

模型名映射来源（供前端把"当前模型"匹配到 provider）：
- config providers 条目的 default_model
- quick_commands 里的 "/model X --provider Y" 目标
- model.default + model.provider
- 适配器自己声明的 match 子串（兜底）

插件运行在 gateway 进程内，直接 import hermes_cli；standalone 测试时
（无 hermes 环境）退化为直接解析 config.yaml + 内置精简注册表。
"""

import os
import re
from pathlib import Path

from usage_adapters.base import get_env

_CONFIG_PATH = Path(os.path.expanduser("~/.hermes/config.yaml"))

# standalone 兜底注册表（gateway 内运行时以 hermes_cli.auth.PROVIDER_REGISTRY 为准）：
# id -> (显示名, key 环境变量组)
_FALLBACK_REGISTRY = {
    "deepseek": ("DeepSeek", ("DEEPSEEK_API_KEY",)),
    "xai": ("xAI", ("XAI_API_KEY",)),
    "zai": ("Z.AI / GLM", ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY")),
    "kimi-coding": ("Kimi / Moonshot", ("KIMI_API_KEY", "KIMI_CODING_API_KEY")),
    "kimi-coding-cn": ("Kimi / Moonshot (China)", ("KIMI_CN_API_KEY",)),
    "minimax": ("MiniMax", ("MINIMAX_API_KEY",)),
    "minimax-cn": ("MiniMax (China)", ("MINIMAX_CN_API_KEY",)),
    "anthropic": ("Anthropic", ("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN")),
    "openai-api": ("OpenAI API", ("OPENAI_API_KEY",)),
    "gemini": ("Google AI Studio", ("GOOGLE_API_KEY", "GEMINI_API_KEY")),
    "alibaba": ("Qwen Cloud", ("DASHSCOPE_API_KEY",)),
    "stepfun": ("StepFun Step Plan", ("STEPFUN_API_KEY",)),
    "xiaomi": ("Xiaomi MiMo", ("XIAOMI_API_KEY",)),
    "openrouter": ("OpenRouter", ("OPENROUTER_API_KEY",)),
}

# OAuth 型 provider：id -> (显示名, 凭证文件)
_OAUTH_PROVIDERS = {
    "openai-codex": ("Codex (ChatGPT)", "~/.codex/auth.json"),
}

# /model <slug> --provider <pid> 的 quick_commands 目标解析
_MODEL_ALIAS_RE = re.compile(r"/model\s+(\S+)\s+--provider\s+(\S+)")


def _load_yaml_config() -> dict:
    try:
        import yaml
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _registry():
    """返回 {id: (name, key_envs)}；gateway 内用官方注册表，否则用兜底表。"""
    try:
        from hermes_cli.auth import PROVIDER_REGISTRY
        return {
            pid: (p.name, tuple(p.api_key_env_vars))
            for pid, p in PROVIDER_REGISTRY.items()
            if p.api_key_env_vars  # 只要 API-key 型；OAuth 型走 _OAUTH_PROVIDERS
        }
    except Exception:
        return dict(_FALLBACK_REGISTRY)


def discover() -> list:
    """枚举已配置的 provider。

    返回 [{id, name, models: [str], source: str}]，只含"有凭证"的：
    - config providers 字典里的条目（用户显式加的）
    - 注册表里 key 环境变量存在的
    - OAuth 凭证文件存在的
    """
    cfg = _load_yaml_config()
    found = {}

    # 1. config.yaml providers（custom 条目）
    for pid, entry in (cfg.get("providers") or {}).items():
        if not isinstance(entry, dict):
            continue
        models = []
        if entry.get("default_model"):
            models.append(entry["default_model"])
        found[pid] = {"id": pid, "name": pid, "models": models, "source": "config"}

    # 2. 内置注册表 + key 存在性
    for pid, (name, key_envs) in _registry().items():
        if pid in found:
            continue
        if any(get_env(k) for k in key_envs):
            found[pid] = {"id": pid, "name": name, "models": [], "source": "registry"}

    # 3. OAuth 凭证文件
    for pid, (name, cred_path) in _OAUTH_PROVIDERS.items():
        if pid in found:
            continue
        if os.path.exists(os.path.expanduser(cred_path)):
            found[pid] = {"id": pid, "name": name, "models": [], "source": "oauth"}

    if not found:
        return []

    # 模型名映射：model.default/provider + quick_commands 目标
    model_cfg = cfg.get("model") or {}
    if model_cfg.get("provider") in found and model_cfg.get("default"):
        found[model_cfg["provider"]]["models"].append(model_cfg["default"])
    for alias in (cfg.get("quick_commands") or {}).values():
        if not isinstance(alias, dict):
            continue
        m = _MODEL_ALIAS_RE.search(str(alias.get("target", "")))
        if m and m.group(2) in found:
            found[m.group(2)]["models"].append(m.group(1))

    # 去重 + 去掉空模型名
    for p in found.values():
        p["models"] = sorted({m for m in p["models"] if m})

    return sorted(found.values(), key=lambda p: p["id"])
