import { useEffect, useState } from "react";
import { collection, onSnapshot, orderBy, query, limit } from "firebase/firestore";
import { db } from "../firebase";
import { GlobalPatternDoc } from "../types";

/** The "gets smarter over time" story: every distinct scam entity AEGIS
 * has cross-referenced across ALL users, growing report_count each time
 * an independent user is targeted by the same sender. */
export function PatternMap() {
  const [patterns, setPatterns] = useState<GlobalPatternDoc[]>([]);

  useEffect(() => {
    const q = query(collection(db, "global_patterns"), orderBy("report_count", "desc"), limit(50));
    return onSnapshot(q, (snap) => {
      setPatterns(snap.docs.map((d) => d.data() as GlobalPatternDoc));
    });
  }, []);

  const maxCount = Math.max(1, ...patterns.map((p) => p.report_count));

  return (
    <div className="flex flex-col gap-2 overflow-y-auto p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
        Shared threat patterns ({patterns.length})
      </div>
      {patterns.length === 0 && (
        <div className="py-8 text-center text-sm text-slate-500">
          No confirmed patterns yet -- these appear once a scam-leaning case is closed.
        </div>
      )}
      {patterns.map((p) => (
        <div
          key={p.pattern_id}
          className="rounded border border-aegis-border bg-aegis-panel p-3 text-sm"
        >
          <div className="mb-1 flex items-center justify-between">
            <span className="font-mono text-xs text-slate-400">{p.pattern_id.slice(0, 16)}...</span>
            <span className="text-xs text-slate-500">{p.entity_type}</span>
          </div>
          {p.claimed_institution && (
            <div className="mb-1 text-sm">
              Impersonates <span className="font-medium">{p.claimed_institution}</span>
            </div>
          )}
          <div className="mb-2 h-1.5 w-full overflow-hidden rounded bg-white/5">
            <div
              className="h-full bg-aegis-danger"
              style={{ width: `${(p.report_count / maxCount) * 100}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>{p.report_count} independent report{p.report_count === 1 ? "" : "s"}</span>
            <span>{Math.round(p.confidence * 100)}% confidence</span>
          </div>
        </div>
      ))}
    </div>
  );
}
