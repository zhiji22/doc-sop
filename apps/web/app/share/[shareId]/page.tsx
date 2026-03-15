"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { fetchPublicRun } from "@/lib/api";
import { runToMarkdown } from "@/lib/markdown";
import { downloadTextFile } from "@/lib/download";

import type { PublicRun } from "@/types";

import { ResultRenderer } from "@/components/result/ResultRenderer";
import { ShareHeader } from "@/components/share/ShareHeader";
import { ShareMeta } from "@/components/share/ShareMeta";

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

  if (loading) {
    return (
      <div style={{ padding: 40 }}>
        <ShareHeader />
        Loading result...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 40 }}>
        <ShareHeader />
        <div style={{ color: "red" }}>{error}</div>
      </div>
    );
  }

  if (!run) {
    return (
      <div
        style={{
          textAlign: "center",
          marginTop: 80,
        }}
      >
        <h2>Result Not Found</h2>

        <p style={{ color: "#666" }}>
          This shared result may have been removed or is no longer public.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        maxWidth: 900,
        margin: "0 auto",
        padding: 32,
      }}
    >
      <ShareHeader />

      <h1 style={{ marginBottom: 8 }}>
        {run.template.toUpperCase()} Result
      </h1>

      <ShareMeta template={run.template} />

      <section
        style={{
          border: "1px solid #eee",
          borderRadius: 12,
          padding: 20,
          background: "#fff",
          marginBottom: 24,
        }}
      >
        {run.status === "done" ? (
          <ResultRenderer run={run as any} />
        ) : run.status === "failed" ? (
          <div style={{ color: "red" }}>
            Failed: {run.error}
          </div>
        ) : (
          <div>Processing...</div>
        )}
      </section>

      {run.status === "done" && (
        <section
          style={{
            border: "1px solid #eee",
            borderRadius: 12,
            padding: 16,
            background: "#fafafa",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 12 }}>
            Export
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={() => {
                const md = runToMarkdown(run as any);
                downloadTextFile(
                  `${run.template}-result.md`,
                  md,
                  "text/markdown;charset=utf-8"
                );
              }}
            >
              Export Markdown
            </button>

            <button
              onClick={() => window.print()}
            >
              Export PDF
            </button>
          </div>
        </section>
      )}
    </div>
  );
}