import IncidentList from "@/components/IncidentList";

export default function Home() {
  return (
    <main className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">OpsAgent-X</h1>
        <p className="text-muted">Autonomous multi-agent DevOps &amp; reliability engineering console.</p>
      </header>
      <IncidentList />
    </main>
  );
}
