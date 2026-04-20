import type { RouteRecordRaw } from 'vue-router'
import { routes } from '@/router/routes'

export type MenuSearchItem = { path: string; title: string }

function normalizePath(base: string, path: string) {
  if (path.startsWith('/')) return path
  const b = base.endsWith('/') ? base.slice(0, -1) : base
  return `${b}/${path}`.replace(/\/+/g, '/')
}

function walk(
  records: RouteRecordRaw[],
  parentPath: string,
  out: MenuSearchItem[]
) {
  for (const r of records) {
    if (r.meta?.public) {
      if (r.children?.length) walk(r.children, parentPath, out)
      continue
    }
    const path = typeof r.path === 'string' ? normalizePath(parentPath, r.path) : parentPath
    const title = r.meta?.title as string | undefined
    if (title && r.name && !String(r.name).includes('redirect')) {
      out.push({ path, title })
    }
    if (r.children?.length) walk(r.children, path === '/' ? '' : path, out)
  }
}

/** 可搜索的菜单项（用于全局搜索，不含登录等公开页） */
export function getFlattenedMenuRoutes(): MenuSearchItem[] {
  const out: MenuSearchItem[] = []
  const root = routes.find((x) => x.path === '/')
  if (root?.children) walk(root.children, '/', out)
  const uniq = new Map<string, MenuSearchItem>()
  for (const item of out) {
    const key = item.path
    if (!uniq.has(key)) uniq.set(key, item)
  }
  return [...uniq.values()]
}
