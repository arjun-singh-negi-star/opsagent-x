export type IncidentStatus =
  | "received"
  | "routing"
  | "diagnosing"
  | "patch_generated"
  | "verified"
  | "verification_failed"
  | "human_reviewed"
  | "auto_approved"
  | "deployed";

export interface Incident {
  incident_id: string;
  alert: {
    source: string;
    severity: string;
    service?: string;
    namespace?: string;
    summary: string;
  };
  status: IncidentStatus;
  current_state?: Record<string, unknown>;
  next_nodes?: string[];
}

export interface AgentEvent {
  agent: string;
  event: string;
  detail?: unknown;
  cost_usd?: number;
  passed?: boolean;
  branch?: string;
}
