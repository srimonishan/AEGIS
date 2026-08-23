import { useEffect, useState } from "react";
import { collection, onSnapshot, orderBy, query, limit } from "firebase/firestore";
import { db } from "../firebase";
import { UserReportDoc, Verdict, CaseStatus } from "../types";

const VERDICT_STYLE: Record<Verdict, string> = {
  scam: "bg-aegis-danger/20 text-red-300 border-aegis-danger/40",
  likely_scam: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  uncertain: "bg-aegis-warn/20 text-amber-300 border-aegis-warn/40",
  likely_safe: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  safe: "bg-aegis-safe/20 text-emerald-300 border-aegis-safe/40",
};

const STATUS_LABEL: Record<CaseStatus, string> = {
  open: "Open",
  awaiting_user: "Awaiting user",
  monitoring: "Monitoring",
  escalated: "Escalated",
  closed: "Closed",
};

export function LiveFeed({
  onSelect,
  selectedId,
}: {
  onSelect: (reportId: string) => void;
  selectedId: string | null;
}) {
  const [reports, setReports] = useState<UserReportDoc[]>([]);

  useEffect(() => {
    const q = query(collection(db, "user_reports"), orderBy("updated_at", "desc"), limit(100));
    return onSnapshot(q, (snap) => {
      setReports(snap.docs.map((d) => d.data() as UserReportDoc));
    });
  }, []);

  return (
    <div className="flex flex-col divide-y divide-aegis-border overflow-y-auto">
      <div className="sticky top-0 bg-aegis-bg px-4 py-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        Live case feed ({reports.length})
      </div>
      {reports.length === 0 && (
        <div className="px-4 py-8 text-center text-sm text-slate-500">
          No cases yet -- forward a message to the AEGIS WhatsApp number to see one appear here.
        </div>
      )}
      {reports.map((r) => (
        <button
          key={r.report_id}
          onClick={() => onSelect(r.report_id)}
          className={`flex w-full flex-col gap-1 px-4 py-3 text-left transition hover:bg-aegis-panel ${
            selectedId === r.report_id ? "bg-aegis-panel" : ""
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-mono text-xs text-slate-500">
              {r.report_id.slice(0, 12)}
            </span>
            {r.verdict && (
              <span
                className={`shrink-0 rounded border px-2 py-0.5 text-[11px] font-medium ${VERDICT_STYLE[r.verdict]}`}
              >
                {r.verdict.replace("_", " ")}
              </span>
            )}
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>{STATUS_LABEL[r.status]}</span>
            {typeof r.confidence === "number" && <span>{Math.round(r.confidence * 100)}% conf.</span>}
          </div>
          {r.manipulation_patterns?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {r.manipulation_patterns.map((p) => (
                <span key={p} className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-400">
                  {p.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </button>
      ))}
    </div>
  );
}
