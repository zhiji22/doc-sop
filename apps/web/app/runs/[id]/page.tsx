"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useParams } from "next/navigation";
import Link from "next/link";

import { fetchRunById } from "@/lib/api";
import type { RunItem } from "@/types";
import { ResultRenderer } from "@/components/result/ResultRenderer";

import { runToMarkdown } from "@/lib/markdown";
import { downloadTextFile } from "@/lib/download";

export default function RunDetailPage() {
  const { getToken } = useAuth();
  const params = useParams();
  const runId = params.id as string;

  const [run, setRun] = useState<RunItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await fetchRunById(getToken, runId);
        setRun(data);
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    }

    if (runId) {
      load();
    }
  }, [runId, getToken]);

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ marginBottom: 16 }}>
        <Link href="/dashboard">← Back to dashboard</Link>
      </div>

      <h1 style={{ marginBottom: 16 }}>Run Detail</h1>

      {loading ? (
        <div>Loading...</div>
      ) : error ? (
        <div style={{ color: "red" }}>{error}</div>
      ) : !run ? (
        <div>Run not found.</div>
      ) : (
        <div style={{ display: "grid", gap: 16 }}>
          <section style={cardStyle}>
            <div><strong>Run ID:</strong> {run.id}</div>
            <div><strong>Template:</strong> {run.template}</div>
            <div><strong>Status:</strong> {run.status}</div>
            <div><strong>Tokens:</strong> {run.usage_tokens ?? "-"}</div>
            <div><strong>Cost:</strong> {run.cost_usd ?? "-"}</div>
            {run.error && (
              <div style={{ color: "red" }}>
                <strong>Error:</strong> {run.error}
              </div>
            )}
            {run.status === "done" && (
                <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
                    <button
                        onClick={() => {
                        const md = runToMarkdown(run);
                        downloadTextFile(`${run.template}-${run.id}.md`, md, "text/markdown;charset=utf-8");
                        }}
                    >
                        Export Markdown
                    </button>
                    <button onClick={() => window.print()}>
                        Export PDF
                    </button>
                </div>
            )}
          </section>

          <section style={cardStyle}>
            {run.status === "done" ? (
              <ResultRenderer run={run} />
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