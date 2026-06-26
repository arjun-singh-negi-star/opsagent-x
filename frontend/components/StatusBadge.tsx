import clsx from "clsx";
import type { IncidentStatus } from "@/lib/types";

const STYLES: Record<string, string> = {
  received: "bg-muted/20 text-muted",
  routing: "bg-accent/20 text-accent",
  diagnosing: "bg-accent/20 text-accent",
  patch_generated: "bg-warn/20 text-warn",
  verified: "bg-ok/20 text-ok",
  verification_failed: "bg-danger/20 text-danger",
  human_reviewed: "bg-warn/20 text-warn",
  auto_approved: "bg-ok/20 text-ok",
  deployed: "bg-ok/20 text-ok",
};

export default function StatusBadge({ status }: { status: IncidentStatus | string }) {
  return (
    <span
      className={clsx(
        "rounded-full px-2.5 py-1 text-xs font-mono uppercase tracking-wide",
        STYLES[status] ?? "bg-muted/20 text-muted"
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
