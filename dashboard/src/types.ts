// Hand-mirrored from shared/schemas/*.py -- the dashboard runs in a
// different language runtime than the services, so this is a manually
// kept-in-sync TypeScript view of the same Firestore document shapes.
// If you change a field there, change it here too.

export type CaseStatus = "open" | "awaiting_user" | "monitoring" | "escalated" | "closed";

export type Verdict = "scam" | "likely_scam" | "uncertain" | "likely_safe" | "safe";

export type ManipulationPattern =
  | "urgency"
  | "authority_impersonation"
  | "too_good_to_be_true"
  | "emotional_exploitation"
  | "payment_request"
  | "credential_phishing"
  | "other";

export interface ReasoningTraceEntry {
  tool: string;
  phase?: "start" | "end";
  args_summary?: Record<string, unknown>;
  result_summary?: unknown;
  decision?: string;
  reason?: string;
  at: string;
}

export interface UserReportDoc {
  report_id: string;
  user_id: string;
  status: CaseStatus;
  verdict?: Verdict;
  confidence?: number;
  manipulation_patterns: ManipulationPattern[];
  matched_pattern_id?: string;
  plain_language_explanation?: string;
  report_draft?: string;
  family_notified: boolean;
  created_at: string;
  updated_at: string;
  reasoning_trace: ReasoningTraceEntry[];
}

export interface GlobalPatternDoc {
  pattern_id: string;
  fingerprint: string;
  entity_type: string;
  manipulation_patterns: ManipulationPattern[];
  claimed_institution?: string;
  first_seen: string;
  last_seen: string;
  report_count: number;
  confidence: number;
}
