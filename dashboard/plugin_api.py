"""model-usage 插件后端：聚合所有 provider 适配器的额度数据。

注意：hermes 的插件加载器用 spec_from_file_location 以扁平模块名加载本文件，
不能用相对导入；因此这里先把本目录注入 sys.path，再按顶层包导入 usage_adapters。

路由（挂载于 /api/plugins/model-usage）：
  GET /providers        已注册的适配器清单
  GET /usage            全部 provider 额度（带缓存，stale-while-error）
  GET /usage/{pid}      单个 provider；?refresh=1 强制刷新
  GET /health           自检
"""

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_PLUGIN_DIR = str(Path(__file__).resolve().parent)
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from fastapi import APIRouter

from usage_adapters import all_adapters, get_adapter
from usage_adapters.base import iso_now
from usage_adapters.discovery import discover

router = APIRouter()

CACHE_TTL_SECONDS = 120          # 正常缓存 2 分钟
_cache = {}                      # pid -> {"t": epoch, "data": dict}
_cache_lock = threading.Lock()


def _adapter_for_provider(pid: str):
    """找服务该 provider 的适配器：先看 serves 声明，再看 id 同名。"""
    for a in all_adapters():
        if pid in (a.serves or []):
            return a
    return get_adapter(pid)


def _merge_match(data: dict, extra_models: list):
    """把 discovery 扫到的模型名合并进 match（适配器声明的子串兜底保留）。"""
    merged = list(dict.fromkeys((data.get("match") or []) + [m.lower() for m in extra_models]))
    data["match"] = merged
    return data


def _fetch_one(adapter, force=False):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(adapter.id)
    if hit and not force and now - hit["t"] < CACHE_TTL_SECONDS:
        return hit["data"]
    try:
        data = adapter.fetch()
    except Exception as e:  # 适配器自己漏网的异常
        data = adapter.fail("adapter_crash", f"{type(e).__name__}: {e}")
    data["fetched_at"] = iso_now()
    if data.get("ok"):
        with _cache_lock:
            _cache[adapter.id] = {"t": now, "data": data}
        return data
    # 失败时若有旧缓存，返回旧数据并标记 stale
    if hit:
        stale = dict(hit["data"])
        stale["stale"] = True
        stale["error"] = data.get("error")
        stale["detail"] = data.get("detail")
        return stale
    return data


@router.get("/providers")
async def providers():
    """已配置的 provider 清单（discovery）+ 各自由哪个适配器服务。"""
    out = []
    for p in discover():
        a = _adapter_for_provider(p["id"])
        out.append({"id": p["id"], "name": p["name"], "models": p["models"],
                    "source": p["source"], "adapter": a.id if a else None})
    return {"providers": out}


@router.get("/usage")
async def usage(refresh: bool = False):
    """聚合：discovery 枚举已配置 provider -> 有适配器的查实时用量，没有的给"未适配"占位。"""
    discovered = discover()
    # 兜底：discovery 一个都没扫到时（配置读不到），退回纯适配器列表
    if not discovered:
        discovered = [{"id": a.id, "name": a.name, "models": [], "source": "adapter"}
                      for a in all_adapters()]

    jobs = []        # (provider_info, adapter|None)
    for p in discovered:
        jobs.append((p, _adapter_for_provider(p["id"])))

    def work(job):
        p, adapter = job
        if adapter is None:
            # 已配置但无适配器：占位条目，前端灰色显示
            return {
                "id": p["id"], "name": p["name"], "ok": True, "kind": "unsupported",
                "match": [p["id"]] + [m.lower() for m in p["models"]],
                "windows": [], "balance": None, "plan": None, "expiry": None,
                "error": None, "detail": "该 provider 暂无公开的用量查询接口，未适配",
                "fetched_at": iso_now(),
            }
        data = _fetch_one(adapter, force=refresh)
        # 以 discovery 的 provider id 为准（一个适配器可服务多家）
        data["id"] = p["id"]
        data.setdefault("name", p["name"])
        return _merge_match(data, p["models"])

    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        results = list(pool.map(work, jobs))
    return {"providers": results, "fetched_at": iso_now()}


@router.get("/usage/{pid}")
async def usage_one(pid: str, refresh: bool = False):
    adapter = _adapter_for_provider(pid)
    if not adapter:
        return {"error": "unknown_provider", "id": pid}
    models = next((p["models"] for p in discover() if p["id"] == pid), [])
    data = _fetch_one(adapter, force=refresh)
    data["id"] = pid
    return _merge_match(data, models)


@router.get("/health")
async def health():
    return {"ok": True, "adapters": len(all_adapters())}
