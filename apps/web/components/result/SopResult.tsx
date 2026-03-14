import type { SopResult } from "@/types";

export function SopResultView({ data }: { data: SopResult }) {
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <section style={cardStyle}>
        <h2 style={{ margin: 0 }}>{data.title || "Untitled SOP"}</h2>
        <p style={{ marginTop: 12 }}>{data.overview || "-"}</p>
      </section>

      <section style={cardStyle}>
        <h3>Steps</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {data.steps?.length ? (
            data.steps.map((step) => (
              <div key={step.step} style={subCardStyle}>
                <div style={{ fontWeight: 700 }}>Step {step.step}</div>
                <div><strong>Action:</strong> {step.action || "-"}</div>
                <div><strong>Owner:</strong> {step.owner || "-"}</div>
                <div><strong>Inputs:</strong> {step.inputs || "-"}</div>
                <div><strong>Outputs:</strong> {step.outputs || "-"}</div>
                <div>
                  <strong>Risks:</strong>
                  {step.risks?.length ? (
                    <ul>
                      {step.risks.map((risk, idx) => (
                        <li key={idx}>{risk}</li>
                      ))}
                    </ul>
                  ) : (
                    <span> -</span>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div>No steps found.</div>
          )}
        </div>
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

const subCardStyle: React.CSSProperties = {
  border: "1px solid #eee",
  borderRadius: 10,
  padding: 12,
  background: "#fafafa",
};