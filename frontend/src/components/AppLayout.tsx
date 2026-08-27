import { NavLink } from 'react-router-dom'

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <nav className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1400px] items-center gap-6 px-4 py-3 sm:px-6">
          <div className="text-sm font-semibold tracking-tight text-slate-900">
            Printing Reconciliation
          </div>
          <div className="flex gap-1 text-sm">
            <NavLink
              to="/printers"
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 ${
                  isActive
                    ? 'bg-slate-100 font-medium text-slate-900'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              Connect to Printer
            </NavLink>
            <NavLink
              to="/automated"
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 ${
                  isActive
                    ? 'bg-slate-100 font-medium text-slate-900'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              Automated Reconciliation
            </NavLink>
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 ${
                  isActive
                    ? 'bg-slate-100 font-medium text-slate-900'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              Manual Reconciliation
            </NavLink>
            <NavLink
              to="/how-to"
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 ${
                  isActive
                    ? 'bg-slate-100 font-medium text-slate-900'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              How to use
            </NavLink>
          </div>
        </div>
      </nav>
      {children}
    </div>
  )
}
