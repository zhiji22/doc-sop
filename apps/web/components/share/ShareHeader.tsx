export function ShareHeader() {
  return (
    <header
      style={{
        borderBottom: "1px solid #eee",
        paddingBottom: 16,
        marginBottom: 24,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <div style={{ fontWeight: 700, fontSize: 18 }}>
        DocSOP AI
      </div>

      <div style={{ fontSize: 13, color: "#666" }}>
        AI Document to SOP / Checklist
      </div>
    </header>
  );
}