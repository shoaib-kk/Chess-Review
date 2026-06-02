interface HeaderProps {
  apiStatus: "checking" | "ok" | "down";
}

export function Header({ apiStatus }: HeaderProps) {
  const statusClass =
    apiStatus === "ok"
      ? "bg-emerald-400"
      : apiStatus === "checking"
        ? "bg-amber-300"
        : "bg-red-400";

  return (
    <header className="flex flex-col gap-4 border-b border-white/10 px-4 py-4 sm:flex-row sm:items-center sm:justify-between lg:px-8">
      <div className="flex items-center gap-3">
        <div className="grid h-11 w-11 place-items-center rounded bg-app-lightSquare text-2xl text-slate-950">
          ♟
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-normal text-slate-50">Chess Game Reviewer</h1>
          <p className="text-sm text-slate-400">Stockfish analysis with Chess.com-style review tools</p>
        </div>
      </div>
      <div className="flex items-center gap-2 rounded border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300">
        <span className={`h-2.5 w-2.5 rounded-full ${statusClass}`} />
        API {apiStatus}
      </div>
    </header>
  );
}
