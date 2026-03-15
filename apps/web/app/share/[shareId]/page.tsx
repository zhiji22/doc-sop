"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchPublicRun } from "@/lib/api";
import type { PublicRun } from "@/types";
import { ResultRenderer } from "@/components/result/ResultRenderer";

export default function SharePage() {
  const params = useParams();
  const shareId = params.shareId as string;

  const [run, setRun] = useState<PublicRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await fetchPublicRun(shareId);
        setRun(data);
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    }

    if (shareId) {
      load();
    }
  }, [shareId]);

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ marginBottom: 16 }}>Shared Result</h1>

      {loading ? (
        <div>Loading...</div>
      ) : error ? (
        <div style={{ color: "red" }}>{error}</div>
      ) : !run ? (
        <div>Shared result not found.</div>
      ) : (
        <div style={{ display: "grid", gap: 16 }}>
          <section style={cardStyle}>
            <div><strong>Template:</strong> {run.template}</div>
            <div><strong>Status:</strong> {run.status}</div>
          </section>

          <section style={cardStyle}>
            {run.status === "done" ? (
              <ResultRenderer run={run as any} />
            ) : run.status === "failed" ? (
              <div style={{ color: "red" }}>Failed: {run.error}</div>
            ) : (
              <div>Current status: {run.status}</div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 12,
  padding: 16,
  background: "#fff",
};