import type { SummaryResult } from "@/types";

export function SummaryResultView({ data }: { data: SummaryResult }) {
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <section style={cardStyle}>
        <h2 style={{ margin: 0 }}>{data.title || "Untitled Summary"}</h2>
        <p style={{ marginTop: 12 }}>{data.overview || "-"}</p>
      </section>

      <section style={cardStyle}>
        <h3>Key Points</h3>
        {data.key_points?.length ? (
          <ul>
            {data.key_points.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        ) : (
          <div>No key points.</div>
        )}
      </section>

      <section style={cardStyle}>
        <h3>Risks</h3>
        {data.risks?.length ? (
          <ul>
            {data.risks.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        ) : (
          <div>No risks.</div>
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