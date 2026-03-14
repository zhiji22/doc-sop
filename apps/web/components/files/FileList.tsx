import type { FileItem } from "@/types";

export function FileList({
  files,
  selectedFileId,
  onSelect,
}: {
  files: FileItem[];
  selectedFileId: string | null;
  onSelect: (file: FileItem) => void;
}) {
  if (files.length === 0) {
    return <div>No files yet.</div>;
  }

  return (
    <div style={{ display: "grid", gap: 8 }}>
      {files.map((file) => {
        const active = selectedFileId === file.id;

        return (
          <button
            key={file.id}
            onClick={() => onSelect(file)}
            style={{
              textAlign: "left",
              border: active ? "2px solid #111" : "1px solid #ddd",
              borderRadius: 10,
              padding: 12,
              background: "#fff",
              cursor: "pointer",
            }}
          >
            <div style={{ fontWeight: 600 }}>{file.filename}</div>
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              {file.mime || "unknown"} · {file.status}
            </div>
            <div style={{ fontSize: 12, color: "#999", marginTop: 4 }}>
              {file.created_at ? new Date(file.created_at).toLocaleString() : "-"}
            </div>
          </button>
        );
      })}
    </div>
  );
}