import type { PurchaseMethod, Store } from '../api'

/** Stores exclusively linked to a purchase method (出張→デリパワ, 宅配→宅配買取). */
export function methodLinkedStoreIds(methods: PurchaseMethod[]): Set<string> {
  return new Set(
    methods.map((m) => m.linked_store_id).filter((id): id is string => Boolean(id)),
  )
}

/** Shop stores selectable when 買取方法 is 店頭 (excludes dispatch/mail-only stores). */
export function shopStores(stores: Store[], methods: PurchaseMethod[]): Store[] {
  const linked = methodLinkedStoreIds(methods)
  const filtered = stores.filter((s) => !linked.has(s.id))
  return filtered.length ? filtered : stores
}

/** Fallback when API has no rows yet (fresh DB before seed). */
const FALLBACK_METHODS: PurchaseMethod[] = [
  {
    id: 'fallback-tennto',
    label: '店頭',
    sort_order: 1,
    is_active: true,
    requires_area: false,
    linked_store_id: null,
  },
  {
    id: 'fallback-shutcho',
    label: '出張',
    sort_order: 2,
    is_active: true,
    requires_area: true,
    linked_store_id: null,
  },
  {
    id: 'fallback-takuhai',
    label: '宅配',
    sort_order: 3,
    is_active: true,
    requires_area: true,
    linked_store_id: null,
  },
]

export function activePurchaseMethods(methods: PurchaseMethod[]): PurchaseMethod[] {
  const source = methods.length ? methods : FALLBACK_METHODS
  return source.filter((m) => m.is_active !== false).sort((a, b) => a.sort_order - b.sort_order)
}

export function findPurchaseMethod(
  methods: PurchaseMethod[],
  label: string,
): PurchaseMethod | undefined {
  return methods.find((m) => m.label === label)
}

/** Resolve 掲載店舗 from 買取方法; returns null when user must pick (店頭). */
export function storeIdForMethod(
  methods: PurchaseMethod[],
  label: string,
): string | null {
  const method = findPurchaseMethod(methods, label)
  return method?.linked_store_id || null
}

export function methodRequiresArea(methods: PurchaseMethod[], label: string): boolean {
  const method = findPurchaseMethod(methods, label)
  return method?.requires_area ?? (label === '出張' || label === '宅配')
}
