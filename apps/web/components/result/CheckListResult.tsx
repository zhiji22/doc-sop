import type { ChecklistResult } from "@/types";

export function ChecklistResultView({ data }: { data: ChecklistResult }) {
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <section style={cardStyle}>
        <h2 style={{ margin: 0 }}>{data.title || "Untitled Checklist"}</h2>
        <p style={{ marginTop: 12 }}>{data.overview || "-"}</p>
      </section>

      <section style={cardStyle}>
        <h3>Checklist</h3>
        {data.checklist?.length ? (
          <ul>
            {data.checklist.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        ) : (
          <div>No checklist items.</div>
        )}
      </section>

      <section style={cardStyle}>
        <h3>Open Questions</h3>
        {data.open_questions?.length ? (
          <ul>
            {data.open_questions.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        ) : (
          <div>No open questions.</div>
        )}
      </section>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 12,
  padding: 16,
  background: "#fff",
};