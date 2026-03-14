import type {
    RunItem,
    SopResult,
    ChecklistResult,
    SummaryResult,
  } from "@/types";
  
export function runToMarkdown(run: RunItem): string {
    if (!run.result_json) {
        return "# Empty Result\n";
    }

    if (run.template === "sop") {
        const data = run.result_json as SopResult;

        const steps = (data.steps || [])
        .map(
            (step) => `
                ## Step ${step.step}
                - **Action:** ${step.action || "-"}
                - **Owner:** ${step.owner || "-"}
                - **Inputs:** ${step.inputs || "-"}
                - **Outputs:** ${step.outputs || "-"}
                - **Risks:** ${(step.risks || []).join(", ") || "-"}
    `
        )
        .join("\n");

        const checklist = (data.checklist || [])
        .map((item) => `- ${item}`)
        .join("\n");

        const openQuestions = (data.open_questions || [])
        .map((item) => `- ${item}`)
        .join("\n");

        return `# ${data.title || "Untitled SOP"}

            ## Overview
            ${data.overview || "-"}

            ${steps}

            ## Checklist
            ${checklist || "-"}

            ## Open Questions
            ${openQuestions || "-"}
        `;
    }

    if (run.template === "checklist") {
        const data = run.result_json as ChecklistResult;

        const checklist = (data.checklist || [])
        .map((item) => `- ${item}`)
        .join("\n");

        const openQuestions = (data.open_questions || [])
        .map((item) => `- ${item}`)
        .join("\n");

        return `# ${data.title || "Untitled Checklist"}

            ## Overview
            ${data.overview || "-"}

            ## Checklist
            ${checklist || "-"}

            ## Open Questions
            ${openQuestions || "-"}
        `;
    }

    if (run.template === "summary") {
        const data = run.result_json as SummaryResult;

        const keyPoints = (data.key_points || [])
        .map((item) => `- ${item}`)
        .join("\n");

        const risks = (data.risks || [])
        .map((item) => `- ${item}`)
        .join("\n");

        const openQuestions = (data.open_questions || [])
        .map((item) => `- ${item}`)
        .join("\n");

        return `# ${data.title || "Untitled Summary"}

            ## Overview
            ${data.overview || "-"}

            ## Key Points
            ${keyPoints || "-"}

            ## Risks
            ${risks || "-"}

            ## Open Questions
            ${openQuestions || "-"}
        `;
    }

    return `# Result\n\n\`\`\`json\n${JSON.stringify(run.result_json, null, 2)}\n\`\`\`\n`;
}