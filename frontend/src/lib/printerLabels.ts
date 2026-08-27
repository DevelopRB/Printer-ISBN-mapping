/** Canonical manual-reconciliation printer labels (slot → IP). */
export const MANUAL_PRINTER_HOSTS: Record<number, string> = {
  1: '192.168.2.7',
  2: '192.168.2.218',
  3: '192.168.2.176',
}

export function manualPrinterLabel(slot: number): string {
  const host = MANUAL_PRINTER_HOSTS[slot]
  return host ? `Printer ${slot} (${host})` : `Printer ${slot}`
}

