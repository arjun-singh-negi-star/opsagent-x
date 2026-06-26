"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listIncidents } from "@/lib/api";
import type { Incident } from "@/lib/types";
import StatusBadge from "./StatusBadge";

export default function IncidentList() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => listIncidents().then(setIncidents).catch((err) => setError(err.message));
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  if (error) {
    return <p className="text-danger">{error}</p>;
  }

  if (incidents.length === 0) {
    return (
      <p className="text-muted">
        No incidents yet. Point an Alertmanager webhook at{" "}
        <code className="font-mono text-ink">/webhook/alert</code> to see one land here.
      </p>
    );
  }

  return (
    <div className="divide-y divide-border rounded-lg border border-border bg-panel">
      {incidents.map((incident) => (
        <Link
          key={incident.incident_id}
          href={`/incidents/${incident.incident_id}`}
          className="flex items-center justify-between px-4 py-3 hover:bg-white/[0.03]"
        >
          <div>
            <p className="font-mono text-sm text-ink">{incident.incident_id.slice(0, 8)}</p>
            <p className="text-sm text-muted">{incident.alert?.summary}</p>
          </div>
          <StatusBadge status={incident.status} />
        </Link>
      ))}
    </div>
  );
}
