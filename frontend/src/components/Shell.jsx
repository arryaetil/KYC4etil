import {LogOut} from "lucide-react";
import {IconButton} from "./IconButton.jsx";

export function Shell({user, onLogout, children, title, actions}) {
  return (
    <div className="min-h-screen bg-[#eef2f5]">
      <header className="bg-[#C8102E]">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-4">
            <div className="flex flex-col leading-none">
              <span className="text-2xl font-black italic text-white tracking-tight">Etil</span>
              <span className="text-[10px] font-medium text-white/70 tracking-wide">research group</span>
            </div>
            {title && <><div className="h-8 w-px bg-white/20" /><h1 className="text-xl font-semibold text-white">{title}</h1></>}
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right text-sm sm:block">
              <div className="font-medium text-white">{user?.naam}</div>
              <div className="text-white/60">{user?.rol}</div>
            </div>
            <IconButton icon={LogOut} variant="ghost" onClick={onLogout} title="Uitloggen" />
          </div>
        </div>
      </header>
      <div className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-end gap-2 px-4 py-3">{actions}</div>
      </div>
      <main className="mx-auto max-w-7xl px-4 py-5">{children}</main>
    </div>
  );
}
