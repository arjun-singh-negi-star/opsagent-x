interface Props {
  tokenUsage?: Record<string, number>;
}

// Illustrative — mirrors backend/app/config.py's TOKEN_COST_PER_1K. Tune
// both against your actual NIM / self-hosted billing plan.
const RATE_PER_1K: Record<string, number> = {
  supervisor: 0.0002,
  security_agent: 0.0002,
  log_analyst: 0.0006,
  code_fixer: 0.0014,
};

export default function TokenCostPanel({ tokenUsage }: Props) {
  const entries = Object.entries(tokenUsage ?? {});
  const totalTokens = entries.reduce((sum, [, tokens]) => sum + tokens, 0);
  const totalCost = entries.reduce(
    (sum, [agent, tokens]) => sum + (tokens / 1000) * (RATE_PER_1K[agent] ?? 0.0002),
    0
  );

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-muted">Estimated cost</span>
        <span className="font-mono text-lg text-ink">${totalCost.toFixed(5)}</span>
      </div>
      <div className="space-y-1">
        {entries.map(([agent, tokens]) => (
          <div key={agent} className="flex justify-between text-sm">
            <span className="text-muted">{agent}</span>
            <span className="font-mono text-ink">{tokens.toLocaleString()} tok</span>
          </div>
        ))}
        {entries.length === 0 && <p className="text-sm text-muted">No tokens spent yet.</p>}
      </div>
      <p className="text-xs text-muted">
        {totalTokens.toLocaleString()} tokens total · rates are illustrative.
      </p>
    </div>
  );
}
