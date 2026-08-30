import { Suspense, lazy } from "react";
import { MarketingSite } from "./MarketingSite";

const OpsConsole = lazy(() => import("./OpsConsole").then((mod) => ({ default: mod.OpsConsole })));

export default function App() {
  if (window.location.pathname !== "/ops") {
    return <MarketingSite />;
  }

  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center text-sm text-slate-500">Loading…</div>}>
      <OpsConsole />
    </Suspense>
  );
}
