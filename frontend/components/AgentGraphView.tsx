const NODES: { id: string; label: string; x: number; y: number }[] = [
  { id: "supervisor", label: "Supervisor", x: 200, y: 16 },
  { id: "log_analyst", label: "LogAnalyst", x: 30, y: 106 },
  { id: "security_agent", label: "SecurityAgent", x: 370, y: 106 },
  { id: "code_fixer", label: "CodeFixer", x: 200, y: 196 },
  { id: "verification", label: "Verification", x: 200, y: 286 },
  { id: "human_in_the_loop", label: "Human-in-the-Loop", x: 200, y: 376 },
  { id: "deploy", label: "Deploy", x: 200, y: 466 },
];

const EDGES: [string, string][] = [
  ["supervisor", "log_analyst"],
  ["supervisor", "security_agent"],
  ["log_analyst", "code_fixer"],
  ["security_agent", "code_fixer"],
  ["code_fixer", "verification"],
  ["verification", "human_in_the_loop"],
  ["human_in_the_loop", "deploy"],
];

function center(node: { x: number; y: number }) {
  return { cx: node.x + 70, cy: node.y + 20 };
}

export default function AgentGraphView({ activeAgent }: { activeAgent?: string }) {
  const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));

  return (
    <svg viewBox="0 0 540 516" className="h-full w-full">
      {EDGES.map(([from, to]) => {
        const a = center(byId[from]);
        const b = center(byId[to]);
        return <line key={`${from}-${to}`} x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy} stroke="#1F2630" strokeWidth={1.5} />;
      })}
      {NODES.map((node) => {
        const active = node.id === activeAgent;
        return (
          <g key={node.id}>
            <rect
              x={node.x}
              y={node.y}
              width={140}
              height={40}
              rx={8}
              fill={active ? "#22D3EE22" : "#11161D"}
              stroke={active ? "#22D3EE" : "#1F2630"}
              strokeWidth={active ? 2 : 1}
            />
            <text
              x={node.x + 70}
              y={node.y + 24}
              textAnchor="middle"
              fontSize={11}
              fontFamily="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
              fill={active ? "#22D3EE" : "#E6EDF3"}
            >
              {node.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
