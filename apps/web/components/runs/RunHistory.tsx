import type { RunItem } from "@/types";

export function RunHistory({
  runs,
  selectedRunId,
  onSelect,
}: {
  runs: RunItem[];
  selectedRunId: string | null;
  onSelect: (run: RunItem) => void;
}) {
  if (runs.length === 0) {
    return <div>No runs yet.</div>;
  }

  return (
    <div style={{ display: "grid", gap: 8 }}>
      {runs.map((run) => {
        const active = selectedRunId === run.id;

        return (
          <button
            key={run.id}
            onClick={() => onSelect(run)}
            style={{
              textAlign: "left",
              border: active ? "2px solid #111" : "1px solid #ddd",
              borderRadius: 10,
              padding: 12,
              background: "#fff",
              cursor: "pointer",
            }}
          >
            <div style={{ fontWeight: 600 }}>{run.template.toUpperCase()}</div>
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              Status: {run.status}
            </div>
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              Tokens: {run.usage_tokens ?? "-"} · Cost: {run.cost_usd ?? "-"}
            </div>
            {run.error && (
              <div style={{ fontSize: 12, color: "red", marginTop: 4 }}>
                {run.error}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}