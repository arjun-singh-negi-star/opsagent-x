"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getIncident, streamIncident } from "@/lib/api";
import type { AgentEvent, Incident } from "@/lib/types";
import AgentGraphView from "@/components/AgentGraphView";
import ExecutionTree from "@/components/ExecutionTree";
import TokenCostPanel from "@/components/TokenCostPanel";
import ApprovalPanel from "@/components/ApprovalPanel";
import StatusBadge from "@/components/StatusBadge";

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;

  const [incident, setIncident] = useState<Incident | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);

  useEffect(() => {
    getIncident(incidentId).then(setIncident).catch(() => {});
  }, [incidentId]);

  useEffect(() => {
    const source = streamIncident(incidentId, (message) => {
      const event = JSON.parse(message.data) as AgentEvent;
      setEvents((prev) => [...prev, event]);
    });
    return () => source.close();
  }, [incidentId]);

  const latestAgent = events[events.length - 1]?.agent;
  const tokenUsage = incident?.current_state?.token_usage as Record<string, number> | undefined;
  const awaitingApproval = incident?.next_nodes?.includes("human_approval");

  return (
    <main className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="font-mono text-xl text-ink">{incidentId.slice(0, 8)}</h1>
          <p className="text-muted">{incident?.alert?.summary}</p>
        </div>
        {incident && <StatusBadge status={incident.status} />}
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-panel p-4">
          <h2 className="mb-3 text-sm font-medium text-muted">Execution graph</h2>
          <AgentGraphView activeAgent={latestAgent} />
        </div>

        <div className="space-y-6">
          <div className="rounded-lg border border-border bg-panel p-4">
            <h2 className="mb-3 text-sm font-medium text-muted">Live timeline</h2>
            <ExecutionTree events={events} />
          </div>

          <div className="rounded-lg border border-border bg-panel p-4">
            <h2 className="mb-3 text-sm font-medium text-muted">Token cost</h2>
            <TokenCostPanel tokenUsage={tokenUsage} />
          </div>

          {awaitingApproval && (
            <div className="rounded-lg border border-warn/40 bg-warn/10 p-4">
              <h2 className="mb-3 text-sm font-medium text-warn">Awaiting your approval</h2>
              <ApprovalPanel incidentId={incidentId} />
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
