import { useState } from "react";
import { useAuthUser, SignInScreen, SignOutButton } from "./AuthGate";
import { LiveFeed } from "./components/LiveFeed";
import { PatternMap } from "./components/PatternMap";
import { CaseDrilldown } from "./components/CaseDrilldown";

type Tab = "feed" | "patterns";

export function OpsConsole() {
  const user = useAuthUser();
  const [tab, setTab] = useState<Tab>("feed");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (user === undefined) {
    return <div className="flex h-screen items-center justify-center text-sm text-slate-500">Loading…</div>;
  }
  if (user === null) {
    return <SignInScreen />;
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-aegis-border px-4 py-3">
        <div className="flex items-center gap-4">
          <h1 className="text-sm font-semibold tracking-wide">AEGIS Ops Console</h1>
          <nav className="flex gap-1 text-xs">
            <TabButton active={tab === "feed"} onClick={() => setTab("feed")}>
              Live Feed
            </TabButton>
            <TabButton active={tab === "patterns"} onClick={() => setTab("patterns")}>
              Pattern Map
            </TabButton>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">{user.email}</span>
          <SignOutButton />
        </div>
      </header>

      <main className="grid flex-1 grid-cols-[320px_1fr] overflow-hidden">
        <div className="overflow-y-auto border-r border-aegis-border">
          {tab === "feed" ? (
            <LiveFeed onSelect={setSelectedId} selectedId={selectedId} />
          ) : (
            <PatternMap />
          )}
        </div>
        <div className="overflow-hidden">
          <CaseDrilldown reportId={selectedId} />
        </div>
      </main>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded px-2 py-1 ${
        active ? "bg-aegis-accent text-white" : "text-slate-400 hover:text-slate-200"
      }`}
    >
      {children}
    </button>
  );
}
