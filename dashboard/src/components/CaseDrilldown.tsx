import { useEffect, useState } from "react";
import { doc, onSnapshot } from "firebase/firestore";
import { db } from "../firebase";
import { UserReportDoc } from "../types";

export function CaseDrilldown({ reportId }: { reportId: string | null }) {
  const [report, setReport] = useState<UserReportDoc | null>(null);

  useEffect(() => {
    if (!reportId) {
      setReport(null);
      return;
    }
    return onSnapshot(doc(db, "user_reports", reportId), (snap) => {
      setReport(snap.exists() ? (snap.data() as UserReportDoc) : null);
    });
  }, [reportId]);

  if (!reportId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        Select a case from the live feed to see the agent's reasoning trace.
      </div>
    );
  }

  if (!report) {
    return <div className="p-4 text-sm text-slate-500">Loading case {reportId}...</div>;
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto p-4">
      <div className="mb-4">
        <div className="mb-1 font-mono text-xs text-slate-500">{report.report_id}</div>
        <h2 className="text-lg font-semibold">
          {report.verdict ? report.verdict.replace(/_/g, " ") : "pending verdict"}
          {typeof report.confidence === "number" && (
            <span className="ml-2 text-sm font-normal text-slate-400">
              {Math.round(report.confidence * 100)}% confidence
            </span>
          )}
        </h2>
      </div>

      {report.plain_language_explanation && (
        <Section title="Explanation delivered to user">
          <p className="text-sm text-slate-300">{report.plain_language_explanation}</p>
        </Section>
      )}

      {report.report_draft && (
        <Section title="Report draft">
          <p className="whitespace-pre-wrap text-sm text-slate-300">{report.report_draft}</p>
        </Section>
      )}

      <Section title={`Agent reasoning trace (${report.reasoning_trace?.length ?? 0} steps)`}>
        <ol className="flex flex-col gap-2">
          {(report.reasoning_trace ?? []).map((entry, i) => (
            <li
              key={i}
              className="rounded border border-aegis-border bg-aegis-panel p-2 text-xs"
            >
              <div className="mb-1 flex items-center justify-between">
                <span className="font-medium text-slate-200">{entry.tool}</span>
                <span className="text-slate-500">{entry.phase ?? entry.decision ?? ""}</span>
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-words text-slate-400">
                {JSON.stringify(entry.args_summary ?? entry.result_summary ?? entry.reason ?? {}, null, 2)}
              </pre>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Case metadata">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-400">
          <dt>Status</dt>
          <dd className="text-slate-200">{report.status}</dd>
          <dt>Family notified</dt>
          <dd className="text-slate-200">{report.family_notified ? "yes" : "no"}</dd>
          <dt>Matched pattern</dt>
          <dd className="truncate text-slate-200">{report.matched_pattern_id ?? "—"}</dd>
        </dl>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">{title}</div>
      {children}
    </div>
  );
}
