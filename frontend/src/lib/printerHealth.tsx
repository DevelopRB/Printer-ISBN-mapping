import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { listNetworkPrinters, testNetworkPrinterConnection } from '../services/api'
import type { ConnectionTestResult, NetworkPrinterConfig } from '../types'
import { ConnectionIssueModal } from '../components/ConnectionIssueModal'

/** Auto health-check interval while the app is open. */
export const HEALTH_POLL_MS = 30_000

export type HealthPhase = 'checking' | 'connected' | 'disconnected'

export type SystemHealthStatus = 'checking' | 'ready' | 'issue' | 'unknown'

export type FailedPrinter = { slot: number; name: string }

export type SlotHealth = {
  phase: HealthPhase
  result?: ConnectionTestResult
  error?: string
  checkedAt?: string
}

export type ConnectionModalPhase = 'issue' | 'checking' | 'restored' | 'failed'

export type ConnectionModalState = {
  phase: ConnectionModalPhase
  printers: FailedPrinter[]
  detail?: string
}

type PrinterHealthContextValue = {
  printers: NetworkPrinterConfig[]
  live: Record<number, SlotHealth>
  systemStatus: SystemHealthStatus
  loadingConfigs: boolean
  configError: string | null
  refreshConfigs: () => Promise<NetworkPrinterConfig[]>
  reloadPrinterNames: () => Promise<void>
  checkSlot: (slot: number) => Promise<boolean>
  checkSlots: (slots: number[]) => Promise<{ slot: number; name: string; ok: boolean }[]>
  applyTestResult: (slot: number, result: ConnectionTestResult) => void
  reportOperationFailures: (failed: FailedPrinter[]) => void
  connectionModal: ConnectionModalState | null
  closeConnectionModal: () => void
  retryConnectionFromModal: () => Promise<void>
}

const PrinterHealthContext = createContext<PrinterHealthContextValue | null>(null)

function shortName(name: string, slot: number): string {
  const match = name.match(/^Printer\s+\d+/i)
  if (match) return match[0]
  return name || `Printer ${slot}`
}

export function PrinterHealthProvider({ children }: { children: ReactNode }) {
  const [printers, setPrinters] = useState<NetworkPrinterConfig[]>([])
  const [live, setLive] = useState<Record<number, SlotHealth>>({})
  const [loadingConfigs, setLoadingConfigs] = useState(true)
  const [configError, setConfigError] = useState<string | null>(null)
  const [systemStatus, setSystemStatus] = useState<SystemHealthStatus>('checking')
  const [connectionModal, setConnectionModal] = useState<ConnectionModalState | null>(null)

  const inFlightRef = useRef<Set<number>>(new Set())
  const printersRef = useRef<NetworkPrinterConfig[]>([])
  const liveRef = useRef<Record<number, SlotHealth>>({})
  const settledPhaseRef = useRef<Record<number, HealthPhase>>({})
  const mountedRef = useRef(true)
  const pollTimerRef = useRef<number | null>(null)
  /** Slots already shown a disconnect transition popup until they reconnect. */
  const transitionNotifiedRef = useRef<Set<number>>(new Set())
  const modalPrintersRef = useRef<FailedPrinter[]>([])

  useEffect(() => {
    printersRef.current = printers
  }, [printers])

  useEffect(() => {
    liveRef.current = live
  }, [live])

  useEffect(() => {
    if (connectionModal) modalPrintersRef.current = connectionModal.printers
  }, [connectionModal])

  const recomputeSystemStatus = useCallback(
    (nextLive: Record<number, SlotHealth>, list: NetworkPrinterConfig[]) => {
      const required = list.filter((p) => p.is_enabled !== false)
      if (!required.length) {
        setSystemStatus('unknown')
        return
      }
      const pending = required.some(
        (p) => !nextLive[p.slot] || nextLive[p.slot].phase === 'checking',
      )
      if (pending) {
        // Keep CHECKING only until first complete round; later polls update silently.
        setSystemStatus((prev) => (prev === 'checking' ? 'checking' : prev))
        return
      }
      const allOk = required.every((p) => nextLive[p.slot]?.phase === 'connected')
      setSystemStatus(allOk ? 'ready' : 'issue')
    },
    [],
  )

  const applyResult = useCallback(
    (slot: number, result: ConnectionTestResult) => {
      if (!mountedRef.current) return
      const prevSettled = settledPhaseRef.current[slot]
      const nextPhase: HealthPhase = result.ok ? 'connected' : 'disconnected'
      settledPhaseRef.current[slot] = nextPhase

      setLive((prev) => {
        const next = {
          ...prev,
          [slot]: {
            phase: nextPhase,
            result,
            checkedAt: result.checked_at,
          },
        }
        recomputeSystemStatus(next, printersRef.current)
        return next
      })

      setPrinters((prev) =>
        prev.map((p) =>
          p.slot === slot
            ? {
                ...p,
                last_connection_ok: result.ok,
                last_connection_category: result.category,
                last_connection_message: result.message,
                last_connection_http_status: result.http_status,
                last_connection_latency_ms: result.latency_ms,
                last_checked_at: result.checked_at,
                password_configured: result.password_configured,
              }
            : p,
        ),
      )

      if (result.ok) {
        transitionNotifiedRef.current.delete(slot)
      } else if (prevSettled === 'connected' && nextPhase === 'disconnected') {
        // One-shot transition notify — never spam on DISCONNECTED → DISCONNECTED.
        if (!transitionNotifiedRef.current.has(slot)) {
          transitionNotifiedRef.current.add(slot)
          const cfg = printersRef.current.find((p) => p.slot === slot)
          const name = shortName(cfg?.name || `Printer ${slot}`, slot)
          setConnectionModal((existing) => {
            // Don't interrupt an active Test Connection flow.
            if (existing && (existing.phase === 'checking' || existing.phase === 'restored')) {
              return existing
            }
            return {
              phase: 'issue',
              printers: [{ slot, name }],
              detail: `${name} could not be reached.`,
            }
          })
        }
      }
    },
    [recomputeSystemStatus],
  )

  const checkSlot = useCallback(
    async (slot: number): Promise<boolean> => {
      if (inFlightRef.current.has(slot)) {
        return liveRef.current[slot]?.phase === 'connected'
      }
      inFlightRef.current.add(slot)
      if (mountedRef.current) {
        setLive((prev) => ({
          ...prev,
          [slot]: {
            phase: 'checking',
            result: prev[slot]?.result,
            checkedAt: prev[slot]?.checkedAt,
          },
        }))
      }
      try {
        const result = await testNetworkPrinterConnection(slot)
        applyResult(slot, result)
        return result.ok
      } catch (err) {
        if (!mountedRef.current) return false
        const checkedAt = new Date().toISOString()
        const prevSettled = settledPhaseRef.current[slot]
        settledPhaseRef.current[slot] = 'disconnected'
        setLive((prev) => {
          const next = {
            ...prev,
            [slot]: {
              phase: 'disconnected' as const,
              error: err instanceof Error ? err.message : 'Connection test failed.',
              checkedAt,
            },
          }
          recomputeSystemStatus(next, printersRef.current)
          return next
        })
        if (prevSettled === 'connected' && !transitionNotifiedRef.current.has(slot)) {
          transitionNotifiedRef.current.add(slot)
          const cfg = printersRef.current.find((p) => p.slot === slot)
          const name = shortName(cfg?.name || `Printer ${slot}`, slot)
          setConnectionModal({
            phase: 'issue',
            printers: [{ slot, name }],
            detail: `${name} could not be reached.`,
          })
        }
        return false
      } finally {
        inFlightRef.current.delete(slot)
      }
    },
    [applyResult, recomputeSystemStatus],
  )

  const checkSlots = useCallback(
    async (slots: number[]) => {
      const unique = [...new Set(slots)]
      const results = await Promise.all(
        unique.map(async (slot) => {
          const cfg = printersRef.current.find((p) => p.slot === slot)
          const name = shortName(cfg?.name || `Printer ${slot}`, slot)
          const ok = await checkSlot(slot)
          return { slot, name, ok }
        }),
      )
      // After a full batch (including first load), finalize banner from live state.
      const nextLive = liveRef.current
      const required = printersRef.current.filter((p) => p.is_enabled !== false)
      if (
        required.length &&
        required.every((p) => nextLive[p.slot] && nextLive[p.slot].phase !== 'checking')
      ) {
        const allOk = required.every((p) => nextLive[p.slot]?.phase === 'connected')
        setSystemStatus(allOk ? 'ready' : 'issue')
      }
      return results
    },
    [checkSlot],
  )

  const refreshConfigs = useCallback(async () => {
    setLoadingConfigs(true)
    setConfigError(null)
    try {
      const rows = await listNetworkPrinters()
      if (!mountedRef.current) return rows
      setPrinters(rows)
      setSystemStatus('checking')
      setLive(
        Object.fromEntries(rows.map((p) => [p.slot, { phase: 'checking' as const }])),
      )
      await checkSlots(rows.map((p) => p.slot))
      return rows
    } catch {
      if (mountedRef.current) {
        setConfigError('Could not load printer configuration. Is the backend running?')
        setSystemStatus('unknown')
      }
      return []
    } finally {
      if (mountedRef.current) setLoadingConfigs(false)
    }
  }, [checkSlots])

  const reloadPrinterNames = useCallback(async () => {
    try {
      const rows = await listNetworkPrinters()
      if (!mountedRef.current) return
      setPrinters(rows)
    } catch {
      /* ignore — names only */
    }
  }, [])

  const reportOperationFailures = useCallback((failed: FailedPrinter[]) => {
    if (!failed.length) return
    const uniq = new Map<number, FailedPrinter>()
    for (const f of failed) {
      uniq.set(f.slot, { slot: f.slot, name: shortName(f.name, f.slot) })
    }
    setConnectionModal({
      phase: 'issue',
      printers: [...uniq.values()].sort((a, b) => a.slot - b.slot),
    })
  }, [])

  const closeConnectionModal = useCallback(() => {
    setConnectionModal(null)
  }, [])

  const retryConnectionFromModal = useCallback(async () => {
    const targets = modalPrintersRef.current
    if (!targets.length) return
    setConnectionModal((prev) =>
      prev
        ? { ...prev, phase: 'checking', detail: undefined }
        : { phase: 'checking', printers: targets },
    )
    const results = await checkSlots(targets.map((t) => t.slot))
    const stillBad = results.filter((r) => !r.ok)
    if (!mountedRef.current) return
    if (stillBad.length === 0) {
      setConnectionModal({
        phase: 'restored',
        printers: targets,
        detail:
          targets.length === 1
            ? 'The printer is connected and ready.'
            : 'The printers are connected and ready.',
      })
      window.setTimeout(() => {
        if (mountedRef.current) setConnectionModal(null)
      }, 1800)
    } else {
      setConnectionModal({
        phase: 'failed',
        printers: stillBad.map((r) => ({ slot: r.slot, name: r.name })),
        detail:
          stillBad.length === 1
            ? `${stillBad[0].name} is still unavailable. Please check the LAN/network connection.`
            : 'These printers are still unavailable. Please check their LAN/network connections.',
      })
    }
  }, [checkSlots])

  useEffect(() => {
    mountedRef.current = true
    void refreshConfigs()

    const scheduleNext = () => {
      if (pollTimerRef.current != null) {
        window.clearTimeout(pollTimerRef.current)
        pollTimerRef.current = null
      }
      pollTimerRef.current = window.setTimeout(() => {
        if (!mountedRef.current) return
        if (document.visibilityState === 'hidden') {
          scheduleNext()
          return
        }
        const slots = printersRef.current.map((p) => p.slot)
        if (slots.length) {
          void checkSlots(slots).finally(() => {
            if (mountedRef.current) scheduleNext()
          })
        } else {
          scheduleNext()
        }
      }, HEALTH_POLL_MS)
    }

    scheduleNext()

    const onVisibility = () => {
      if (document.visibilityState === 'visible' && mountedRef.current) {
        const slots = printersRef.current.map((p) => p.slot)
        if (slots.length) void checkSlots(slots)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      mountedRef.current = false
      document.removeEventListener('visibilitychange', onVisibility)
      if (pollTimerRef.current != null) {
        window.clearTimeout(pollTimerRef.current)
        pollTimerRef.current = null
      }
      inFlightRef.current.clear()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const value = useMemo<PrinterHealthContextValue>(
    () => ({
      printers,
      live,
      systemStatus,
      loadingConfigs,
      configError,
      refreshConfigs,
      reloadPrinterNames,
      checkSlot,
      checkSlots,
      applyTestResult: applyResult,
      reportOperationFailures,
      connectionModal,
      closeConnectionModal,
      retryConnectionFromModal,
    }),
    [
      printers,
      live,
      systemStatus,
      loadingConfigs,
      configError,
      refreshConfigs,
      reloadPrinterNames,
      checkSlot,
      checkSlots,
      applyResult,
      reportOperationFailures,
      connectionModal,
      closeConnectionModal,
      retryConnectionFromModal,
    ],
  )

  return (
    <PrinterHealthContext.Provider value={value}>
      {children}
      <ConnectionIssueModal
        state={connectionModal}
        onClose={closeConnectionModal}
        onTest={() => void retryConnectionFromModal()}
      />
    </PrinterHealthContext.Provider>
  )
}

export function usePrinterHealth(): PrinterHealthContextValue {
  const ctx = useContext(PrinterHealthContext)
  if (!ctx) {
    throw new Error('usePrinterHealth must be used within PrinterHealthProvider')
  }
  return ctx
}

export function usePrinterHealthOptional(): PrinterHealthContextValue | null {
  return useContext(PrinterHealthContext)
}
