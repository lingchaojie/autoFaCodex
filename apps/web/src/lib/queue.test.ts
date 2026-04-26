import { describe, expect, it, vi } from "vitest";
import { buildWorkflowJob } from "./queue";

describe("buildWorkflowJob", () => {
  it("creates a language-neutral pdf_to_ppt job payload", () => {
    const job = buildWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" });
    expect(job).toEqual({
      task_id: "task_1",
      workflow_type: "pdf_to_ppt"
    });
  });
});
