import { NavLink } from 'react-router-dom'
import { BookOpen, Cable, RefreshCw, Upload } from 'lucide-react'

const linkBase =
  'inline-flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors duration-150 sm:px-3'

const linkActive = 'bg-[var(--accent)] font-semibold text-white shadow-sm'
const linkInactive =
  'font-medium text-slate-600 hover:bg-sky-50 hover:text-sky-900'

const appVersion = (
  window as Window & { printingReconciliation?: { version?: string | null } }
).printingReconciliation?.version

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <nav className="app-navbar sticky top-0 z-50 border-b border-slate-200/90 bg-white/95 shadow-[0_1px_3px_rgb(15_23_42/0.06)] backdrop-blur-md">
        <div className="mx-auto flex max-w-[1400px] items-center gap-2 px-3 py-2 sm:gap-4 sm:px-6 sm:py-2.5">
          <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-4">
            <div className="flex shrink-0 items-center gap-2 sm:gap-2.5">
              <div
                className="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white"
                style={{ background: 'var(--accent)' }}
                aria-hidden
              >
                PR
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold tracking-tight text-slate-900">
                  Printing Reconciliation
                  {appVersion && (
                    <span className="ml-1.5 text-[11px] font-normal text-slate-400">
                      v{appVersion}
                    </span>
                  )}
                </div>
                <div className="hidden text-[11px] text-slate-400 lg:block">
                  Operations print tracking
                </div>
              </div>
            </div>

            <div className="flex min-w-0 flex-wrap items-center gap-0.5 sm:gap-1">
              <NavLink
                to="/automated"
                className={({ isActive }) =>
                  `${linkBase} ${isActive ? linkActive : linkInactive}`
                }
              >
                <RefreshCw size={15} aria-hidden className="hidden sm:inline" />
                <span className="whitespace-nowrap">
                  <span className="sm:hidden">Automated</span>
                  <span className="hidden sm:inline">Automated Reconciliation</span>
                </span>
              </NavLink>

              <NavLink
                to="/manual"
                end
                title="Emergency / Fallback"
                className={({ isActive }) =>
                  `${linkBase} ${isActive ? linkActive : linkInactive}`
                }
              >
                {({ isActive }) => (
                  <>
                    <Upload size={15} aria-hidden className="hidden sm:inline" />
                    <span className="inline-flex flex-col items-start leading-tight sm:flex-row sm:items-baseline sm:gap-1.5">
                      <span className="whitespace-nowrap">
                        <span className="sm:hidden">Manual</span>
                        <span className="hidden sm:inline">Manual Reconciliation</span>
                      </span>
                      <span
                        className={`hidden text-[10px] font-normal md:inline sm:text-xs ${
                          isActive ? 'text-white/80' : 'text-slate-400'
                        }`}
                      >
                        Emergency / Fallback
                      </span>
                    </span>
                  </>
                )}
              </NavLink>

              <NavLink
                to="/printers"
                className={({ isActive }) =>
                  `${linkBase} ${isActive ? linkActive : linkInactive}`
                }
              >
                <Cable size={15} aria-hidden className="hidden sm:inline" />
                <span className="whitespace-nowrap">
                  <span className="sm:hidden">Printers</span>
                  <span className="hidden sm:inline">Connect to Printer</span>
                </span>
              </NavLink>

              <NavLink
                to="/how-to"
                className={({ isActive }) =>
                  `${linkBase} ${isActive ? linkActive : linkInactive}`
                }
              >
                <BookOpen size={15} aria-hidden className="hidden sm:inline" />
                <span className="whitespace-nowrap">How to use</span>
              </NavLink>
            </div>
          </div>

          <div className="ml-auto flex shrink-0 items-center self-center pl-2">
            <img
              src="/gyanbooks-logo.webp"
              alt="Gyan Books Pvt. Ltd."
              className="h-8 w-auto max-w-[140px] object-contain object-right sm:h-9 sm:max-w-[180px] md:h-10 md:max-w-[220px]"
              decoding="async"
            />
          </div>
        </div>
      </nav>
      {children}
    </div>
  )
}
