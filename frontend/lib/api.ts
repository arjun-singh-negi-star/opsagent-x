const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function listIncidents() {
  const res = await fetch(`${API_BASE}/incidents`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load incidents");
  return res.json();
}

export async function getIncident(id: string) {
  const res = await fetch(`${API_BASE}/incidents/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load incident");
  return res.json();
}

export async function approveIncident(id: string, approved: boolean, note?: string) {
  const res = await fetch(`${API_BASE}/incidents/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved, note }),
  });
  if (!res.ok) throw new Error("Failed to record approval");
  return res.json();
}

export function streamIncident(id: string, onEvent: (event: MessageEvent) => void) {
  const source = new EventSource(`${API_BASE}/incidents/${id}/stream`);
  source.onmessage = onEvent;
  return source;
}
