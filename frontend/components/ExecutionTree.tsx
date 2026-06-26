import type { AgentEvent } from "@/lib/types";

const AGENT_LABEL: Record<string, string> = {
  supervisor: "Supervisor",
  log_analyst: "LogAnalyst",
  security_agent: "SecurityAgent",
  code_fixer: "CodeFixer",
  verification: "Verification",
  human_in_the_loop: "Human-in-the-Loop",
  deploy: "Deploy",
  graph: "Graph",
};

export default function ExecutionTree({ events }: { events: AgentEvent[] }) {
  if (events.length === 0) {
    return <p className="text-muted">Waiting for the first agent event…</p>;
  }

  return (
    <ol className="relative space-y-4 border-l border-border pl-4">
      {events.map((event, index) => (
        <li key={index} className="relative">
          <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full bg-accent" />
          <p className="font-mono text-sm text-ink">
            {AGENT_LABEL[event.agent] ?? event.agent} <span className="text-muted">— {event.event}</span>
          </p>
          {typeof event.cost_usd === "number" && (
            <p className="text-xs text-muted">${event.cost_usd.toFixed(5)} estimated</p>
          )}
        </li>
      ))}
    </ol>
  );
}
