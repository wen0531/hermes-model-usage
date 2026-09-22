// model-usage 桌面插件：状态栏显示当前模型 + 各订阅实时用量
// 数据来自本插件 Python 后端 /api/plugins/model-usage（ctx.rest），key 不出后端。
import { host, useValue, useQuery, useQueryClient, STATUSBAR_AREAS, relativeTime, profileColor, Popover, PopoverTrigger, PopoverContent } from '@hermes/plugin-sdk'
import { jsx, jsxs, Fragment } from 'react/jsx-runtime'
import { useState } from 'react'

// provider 的摘要指标：配额型取最高窗口用量%，余额型取 ¥ 整数
function metricOf(p) {
  if (p.balance) {
    const n = Math.round(parseFloat(p.balance.amount))
    return isNaN(n) ? '¥?' : '¥' + n
  }
  let worst = null
  for (const w of p.windows || []) {
    if (w.used_percent != null && (worst === null || w.used_percent > worst)) worst = w.used_percent
  }
  return worst === null ? null : worst + '%'
}

// 当前模型 -> provider：模型名小写后命中 adapter.match 任一子串即匹配
function providerForModel(providers, model) {
  if (!model) return null
  const m = String(model).toLowerCase()
  return (providers || []).find(p => (p.match || []).some(s => m.includes(String(s).toLowerCase()))) || null
}

// 状态栏上单个 provider 的展示段：配额型显示全部窗口（5h/周），余额型显示 ¥
function providerSegments(p) {
  if (p.kind === 'unsupported') {
    return [jsx('span', { key: p.id + '-na', className: 'text-(--ui-text-quaternary)', children: '未适配' })]
  }
  const color = profileColor(p.id)
  if (p.balance) {
    const n = Math.round(parseFloat(p.balance.amount))
    return [jsx('span', { key: p.id + '-bal', style: { color }, children: isNaN(n) ? '¥?' : '¥' + n })]
  }
  const out = []
  for (const w of p.windows || []) {
    if (w.used_percent == null) continue
    if (out.length > 0) out.push(jsx('span', { key: p.id + w.label + '-sep', className: 'text-(--ui-text-quaternary)', children: ' ' }))
    // 窗口标签缩写：5小时 -> 5h，本周 -> 周
    const short = w.label.replace('小时', 'h').replace('本周', '周')
    out.push(jsx('span', { key: p.id + w.label, children: [
      jsx('span', { className: 'text-(--ui-text-tertiary)', children: short + ' ' }),
      jsx('span', { style: { color }, children: w.used_percent + '%' }),
    ] }))
  }
  return out
}

// ---- 详情面板小组件 ----

function Bar({ percent, color }) {
  const p = Math.max(0, Math.min(100, percent ?? 0))
  return jsx('div', {
    className: 'h-1.5 w-full rounded-full overflow-hidden',
    style: { background: 'var(--ui-stroke-secondary)' },
    children: jsx('div', {
      className: 'h-full rounded-full',
      style: { width: p + '%', background: color || 'var(--ui-accent)', opacity: 0.45 + (p / 100) * 0.55 },
    }),
  })
}

function WindowRow({ w, color }) {
  const pct = w.used_percent ?? 0
  let reset = ''
  try { reset = w.reset_at ? relativeTime(w.reset_at) + '重置' : '' } catch (e) { reset = '' }
  const counts = (w.used != null && w.limit != null) ? ` · ${w.used}/${w.limit} 次` : ''
  return jsxs('div', {
    className: 'flex flex-col gap-1',
    children: [
      jsxs('div', {
        className: 'flex justify-between text-[0.6875rem]',
        children: [
          jsx('span', { className: 'text-(--ui-text-secondary)', children: w.label + (pct >= 80 ? ' ⚠' : '') }),
          jsx('span', { className: 'text-(--ui-text-tertiary)', children: `${pct}%${counts}${reset ? ' · ' + reset : ''}` }),
        ],
      }),
      jsx(Bar, { percent: pct, color }),
    ],
  })
}

function ProviderName({ p }) {
  return jsx('span', {
    className: 'text-[0.75rem] font-medium',
    style: { color: profileColor(p.id) },
    children: p.name,
  })
}

function ProviderCard({ p }) {
  // 已配置但无用量接口的 provider：灰色占位
  if (p.kind === 'unsupported') {
    return jsxs('div', {
      className: 'flex flex-col gap-0.5 py-1 opacity-60',
      children: [
        jsx('span', { className: 'text-[0.75rem] font-medium text-(--ui-text-tertiary)', children: p.name }),
        jsx('span', { className: 'text-[0.6875rem] text-(--ui-text-quaternary)', children: p.detail || '未适配' }),
      ],
    })
  }
  if (!p.ok && !(p.windows || []).length && !p.balance) {
    return jsxs('div', {
      className: 'flex flex-col gap-0.5 py-1',
      children: [
        jsx(ProviderName, { p }),
        jsx('span', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: p.detail || p.error || '查询失败' }),
      ],
    })
  }
  const color = profileColor(p.id)
  const children = [
    jsxs('div', {
      className: 'flex items-baseline gap-1.5',
      children: [
        jsx(ProviderName, { p }),
        p.plan ? jsx('span', { className: 'text-[0.625rem] text-(--ui-text-tertiary)', children: p.plan }) : null,
        p.stale ? jsx('span', { className: 'text-[0.625rem] text-(--ui-text-tertiary)', children: '（缓存）' }) : null,
      ].filter(Boolean),
    }),
  ]
  for (const w of p.windows || []) children.push(jsx(WindowRow, { w, color, key: w.label }))
  if (p.balance) {
    children.push(jsx('div', {
      className: 'text-[0.6875rem] text-(--ui-text-secondary)',
      children: `余额 ${p.balance.currency === 'CNY' ? '¥' : ''}${p.balance.amount}`,
    }))
  }
  return jsx('div', { className: 'flex flex-col gap-1.5 py-1.5', children })
}

// 未适配 provider 的折叠区：一行摘要，点开才逐个列出
function UnsupportedSection({ items }) {
  const [open, setOpen] = useState(false)
  if (!items.length) return null
  return jsxs('div', {
    className: 'px-3 py-1.5 border-t border-(--ui-stroke-secondary)',
    children: [
      jsxs('button', {
        type: 'button',
        className: 'w-full flex items-center justify-between text-[0.6875rem] text-(--ui-text-tertiary) hover:text-(--ui-text-secondary)',
        onClick: () => setOpen(!open),
        children: [
          jsx('span', { children: `还有 ${items.length} 个已配置 provider 无用量接口` }),
          jsx('span', { children: open ? '▾' : '▸' }),
        ],
      }),
      open ? jsx('div', {
        className: 'flex flex-col divide-y divide-(--ui-stroke-secondary)',
        children: items.map((p) => jsx(ProviderCard, { p, key: p.id })),
      }) : null,
    ].filter(Boolean),
  })
}

function PanelBody({ data, error, errorDetail, onRefresh }) {
  const providers = data?.providers || []
  const supported = providers.filter((p) => p.kind !== 'unsupported')
  const unsupported = providers.filter((p) => p.kind === 'unsupported')
  const body = error
    ? jsxs('div', {
        className: 'flex flex-col gap-1 p-3 text-[0.6875rem] text-(--ui-text-tertiary)',
        children: [
          jsx('span', { children: '后端请求失败，错误如下：' }),
          jsx('span', { className: 'break-all', children: errorDetail || '未知错误' }),
        ],
      })
    : jsxs(Fragment, {
        children: [
          jsx('div', {
            className: 'flex flex-col divide-y divide-(--ui-stroke-secondary) px-3 py-1',
            children: supported.map((p) => jsx(ProviderCard, { p, key: p.id })),
          }),
          jsx(UnsupportedSection, { items: unsupported }),
        ],
      })
  return jsxs(Fragment, {
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between px-3 pt-2',
        children: [
          jsx('span', { className: 'text-[0.6875rem] font-medium text-(--ui-text-secondary)', children: '订阅用量' }),
          jsx('button', {
            type: 'button',
            className: 'text-[0.6875rem] text-(--ui-text-tertiary) hover:text-(--ui-text-secondary)',
            onClick: onRefresh,
            children: '刷新',
          }),
        ],
      }),
      body,
    ],
  })
}

// ---- 状态栏条目 ----

function makeChip(ctx) {
  return function Chip() {
    const qc = useQueryClient()
    const model = useValue(host.state.model)
    const { data, error } = useQuery({
      queryKey: ['model-usage', 'usage'],
      queryFn: () => ctx.rest('/usage'),
      refetchInterval: 180_000,   // 3 分钟轮询；后端另有 2 分钟缓存
      retry: false,
    })
    const forceRefresh = async () => {
      try { await ctx.rest('/usage?refresh=1') } catch (e) { /* 后端未启用时静默 */ }
      qc.invalidateQueries({ queryKey: ['model-usage', 'usage'] })
    }
    // 状态栏：只显示当前模型对应的 provider；匹配不到（未知模型）时退化为全量列表
    const providers = data?.providers || []
    const current = providerForModel(providers, model)
    const segments = []
    if (error) segments.push(jsx('span', { key: 'err', children: '⚠' }))
    if (current) {
      segments.push(...providerSegments(current))
    } else {
      for (const p of providers) {
        const m = metricOf(p)
        if (m === null) continue
        if (segments.length > 0) {
          segments.push(jsx('span', { key: p.id + '-dot', className: 'text-(--ui-text-quaternary)', children: ' · ' }))
        }
        segments.push(jsx('span', {
          key: p.id,
          style: { color: profileColor(p.id) },
          children: m,
        }))
      }
    }
    if (segments.length === 0 && !error) {
      segments.push(jsx('span', { key: 'loading', className: 'text-(--ui-text-quaternary)', children: '…' }))
    }
    return jsxs(Popover, {
      children: [
        jsx(PopoverTrigger, {
          asChild: true,
          children: jsx('button', {
            type: 'button',
            className: 'px-1.5 text-[0.6875rem] hover:text-(--ui-text-secondary)',
            children: segments,
          }),
        }),
        jsx(PopoverContent, {
          side: 'top',
          align: 'end',
          className: 'w-72',
          children: jsx(PanelBody, {
            data, error: !!error,
            errorDetail: error ? String(error?.message || error) : '',
            onRefresh: forceRefresh,
          }),
        }),
      ],
    })
  }
}

export default {
  id: 'model-usage',
  name: 'Model Usage',
  defaultEnabled: true,
  register(ctx) {
    const Chip = makeChip(ctx)
    ctx.register({
      id: 'chip',
      area: STATUSBAR_AREAS.right,
      order: 120,
      render: () => jsx(Chip, {}),
    })
  },
}
