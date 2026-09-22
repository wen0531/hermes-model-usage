"""适配器注册表：扫描本目录所有 .py，收集模块级 ADAPTER 实例。

新增 provider = 丢一个定义了 ADAPTER 的文件进来，重启 gateway 即生效。
"""

import importlib
import pkgutil
from pathlib import Path

from .base import UsageAdapter

_REGISTRY: dict = {}


def _load_all():
    pkg_dir = Path(__file__).parent
    pkg_name = __name__
    for mod in pkgutil.iter_modules([str(pkg_dir)]):
        if mod.name in ("base", "discovery", "__init__"):
            continue
        try:
            m = importlib.import_module(f"{pkg_name}.{mod.name}")
        except Exception:
            continue  # 单个适配器坏了不拖垮整体
        adapter = getattr(m, "ADAPTER", None)
        if isinstance(adapter, UsageAdapter):
            _REGISTRY[adapter.id] = adapter


_load_all()


def all_adapters() -> list:
    return list(_REGISTRY.values())


def get_adapter(adapter_id: str):
    return _REGISTRY.get(adapter_id)
