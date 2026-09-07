import {LogOut, Settings} from "lucide-react";
import {classNames} from "../lib/format.js";

const MODULES = [
  ["onderzoek", "Onderzoek"],
  ["monitoring", "Jaarverslagenmonitoring"],
];

export function AppShell({user, module, onModule, onLogout, children}) {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white">
      <header>
        <div className="flex items-center justify-between gap-6 px-6 py-3">
          <div className="flex items-center gap-8">
            <img
              src="/etil-merk-night.png"
              alt="Etil"
              className="h-auto w-[72px]"
            />
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
                      : "text-mist-50 hover:text-ink",
                  )}
                >
                  {label}
                </button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-mist-65 sm:block">
              {user?.naam}
            </span>
            <button
              type="button"
              onClick={() => onModule("instellingen")}
              title="Instellingen"
              aria-label="Instellingen"
              aria-current={module === "instellingen" ? "page" : undefined}
              className={classNames(
                "focus-ring rounded-md p-2 transition hover:bg-panel hover:text-ink",
                module === "instellingen" ? "bg-panel text-ink" : "text-mist-25",
              )}
            >
              <Settings size={17} />
            </button>
            <button
              type="button"
              onClick={onLogout}
              title="Uitloggen"
              aria-label="Uitloggen"
              className="focus-ring rounded-md p-2 text-mist-25 transition hover:bg-panel hover:text-ink"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
        {/* Hetzelfde streepje als in het Etil-logo. Dit is de enige plek waar
            het merk in het werkscherm kleur krijgt; verder is alles Night. */}
        <div aria-hidden="true" className="data-verloop h-0.5" />
      </header>
      <main className="flex min-h-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
