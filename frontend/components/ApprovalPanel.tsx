"use client";

import { useState } from "react";
import { approveIncident } from "@/lib/api";

export default function ApprovalPanel({ incidentId }: { incidentId: string }) {
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<"approved" | "rejected" | null>(null);

  async function handleDecision(approved: boolean) {
    setSubmitting(true);
    try {
      await approveIncident(incidentId, approved);
      setDone(approved ? "approved" : "rejected");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <p className="text-sm text-muted">
        Patch {done}. {done === "approved" ? "Deployment requested." : "Workflow ended without deploying."}
      </p>
    );
  }

  return (
    <div className="flex gap-3">
      <button
        onClick={() => handleDecision(true)}
        disabled={submitting}
        className="rounded-md bg-ok/20 px-4 py-2 text-sm font-medium text-ok hover:bg-ok/30 disabled:opacity-50"
      >
        Approve &amp; deploy
      </button>
      <button
        onClick={() => handleDecision(false)}
        disabled={submitting}
        className="rounded-md bg-danger/20 px-4 py-2 text-sm font-medium text-danger hover:bg-danger/30 disabled:opacity-50"
      >
        Reject
      </button>
    </div>
  );
}
