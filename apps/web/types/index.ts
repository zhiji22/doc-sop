export type FileItem = {
    id: string;
    user_id: string;
    filename: string;
    storage_key: string;
    mime: string | null;
    size: number | null;
    status: string;
    created_at: string | null;
  };
  
export type RunItem = {
    id: string;
    user_id: string;
    file_id: string;
    template: "sop" | "checklist" | "summary";
    status: "queued" | "running" | "done" | "failed";
    result_json: any | null;
    error: string | null;
    usage_tokens: number | null;
    cost_usd: number | null;
};

export type SopResult = {
    title: string;
    overview: string;
    steps: Array<{
        step: number;
        action: string;
        owner: string;
        inputs: string;
        outputs: string;
        risks: string[];
    }>;
    checklist: string[];
    open_questions: string[];
};
  
export type ChecklistResult = {
    title: string;
    overview: string;
    checklist: string[];
    open_questions: string[];
};

export type SummaryResult = {
    title: string;
    overview: string;
    key_points: string[];
    risks: string[];
    open_questions: string[];
};