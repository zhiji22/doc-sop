"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useParams } from "next/navigation";
import Link from "next/link";

import { fetchRunById, shareRun, unshareRun } from "@/lib/api";
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

    const [shareUrl, setShareUrl] = useState("");
    const [shareLoading, setShareLoading] = useState(false);

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

    useEffect(() => {
        if (run?.is_public && run.share_id) {
          setShareUrl(`${process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"}/share/${run.share_id}`);
        } else {
          setShareUrl("");
        }
      }, [run]);

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
                            <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
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

                                {!run.is_public ? (
                                <button
                                    onClick={async () => {
                                    try {
                                        setShareLoading(true);
                                        const data = await shareRun(getToken, run.id);
                                        setShareUrl(data.share_url);
                                        setRun((prev) =>
                                        prev
                                            ? {
                                                ...prev,
                                                is_public: true,
                                                share_id: data.share_id,
                                            }
                                            : prev
                                        );
                                    } catch (err) {
                                        setError(String(err));
                                    } finally {
                                        setShareLoading(false);
                                    }
                                    }}
                                >
                                    {shareLoading ? "Sharing..." : "Create Share Link"}
                                </button>
                                ) : (
                                <button
                                    onClick={async () => {
                                    try {
                                        setShareLoading(true);
                                        await unshareRun(getToken, run.id);
                                        setShareUrl("");
                                        setRun((prev) =>
                                        prev
                                            ? {
                                                ...prev,
                                                is_public: false,
                                            }
                                            : prev
                                        );
                                    } catch (err) {
                                        setError(String(err));
                                    } finally {
                                        setShareLoading(false);
                                    }
                                    }}
                                >
                                    {shareLoading ? "Updating..." : "Disable Share"}
                                </button>
                                )}
                            </div>
                            )}
                        {run?.status === "done" && (
                        <div style={{ marginTop: 16 }}>
                            <div style={{ fontWeight: 600, marginBottom: 8 }}>Share Status</div>
                            <div
                            style={{
                                border: "1px solid #ddd",
                                borderRadius: 8,
                                padding: 12,
                                background: "#fafafa",
                            }}
                            >
                            {run.is_public ? "Public" : "Private"}
                            </div>

                            {run.is_public && shareUrl && (
                            <>
                                <div
                                style={{
                                    marginTop: 12,
                                    border: "1px solid #ddd",
                                    borderRadius: 8,
                                    padding: 12,
                                    background: "#fff",
                                    wordBreak: "break-all",
                                }}
                                >
                                {shareUrl}
                                </div>

                                <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                                <button
                                    onClick={async () => {
                                    await navigator.clipboard.writeText(shareUrl);
                                    }}
                                >
                                    Copy Link
                                </button>

                                <a href={shareUrl} target="_blank" rel="noreferrer">
                                    Open Share Page
                                </a>
                                </div>
                            </>
                            )}
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