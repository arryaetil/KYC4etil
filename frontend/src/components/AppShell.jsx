import {LogOut} from "lucide-react";
import {classNames} from "../lib/format.js";

const MODULES = [
  ["onderzoek", "Onderzoek"],
  ["monitoring", "Jaarverslagenmonitoring"],
];

export function AppShell({user, module, onModule, onLogout, children}) {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="border-b border-line">
        <div className="flex items-center justify-between gap-6 px-6 py-3">
          <div className="flex items-center gap-8">
            <div className="flex flex-col leading-none">
              <span className="text-lg font-black italic tracking-tight text-[#C8102E]">
                Etil
              </span>
              <span className="text-[9px] font-medium tracking-wide text-slate-400">
                research group
              </span>
            </div>
            <nav className="flex items-center gap-1" aria-label="Modules">
              {MODULES.map(([sleutel, label]) => (
                <button
                  key={sleutel}
                  type="button"
                  aria-current={module === sleutel ? "page" : undefined}
                  onClick={() => onModule(sleutel)}
                  className={classNames(
                    "focus-ring rounded-md px-3 py-1.5 text-sm transition",
                    module === sleutel
                      ? "bg-panel font-semibold text-ink"
                      : "text-slate-500 hover:text-ink",
                  )}
                >
                  {label}
                </button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-slate-500 sm:block">
              {user?.naam}
            </span>
            <button
              type="button"
              onClick={onLogout}
              title="Uitloggen"
              aria-label="Uitloggen"
              className="focus-ring rounded-md p-2 text-slate-400 transition hover:bg-panel hover:text-ink"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </header>
      <main className="flex min-h-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
