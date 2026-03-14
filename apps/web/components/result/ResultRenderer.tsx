import type { RunItem, SopResult, ChecklistResult, SummaryResult } from "@/types";
import { SopResultView } from "./SopResult";
import { ChecklistResultView } from "./CheckListResult";
import { SummaryResultView } from "./SummaryResult";

export function ResultRenderer({ run }: { run: RunItem }) {
  if (!run.result_json) {
    return <div>No result yet.</div>;
  }

  if (run.template === "sop") {
    return <SopResultView data={run.result_json as SopResult} />;
  }

  if (run.template === "checklist") {
    return <ChecklistResultView data={run.result_json as ChecklistResult} />;
  }

  if (run.template === "summary") {
    return <SummaryResultView data={run.result_json as SummaryResult} />;
  }

  return (
    <pre style={{ whiteSpace: "pre-wrap", overflowX: "auto" }}>
      {JSON.stringify(run.result_json, null, 2)}
    </pre>
  );
}