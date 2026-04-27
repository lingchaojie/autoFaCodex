import Redis from "ioredis";

export type WorkflowJobInput = {
  taskId: string;
  workflowType: "pdf_to_ppt";
  mode?: "initial" | "repair";
};

export function buildWorkflowJob(input: WorkflowJobInput) {
  return {
    task_id: input.taskId,
    workflow_type: input.workflowType,
    mode: input.mode ?? "initial"
  };
}

export async function enqueueWorkflowJob(input: WorkflowJobInput) {
  const redis = new Redis(process.env.REDIS_URL ?? "redis://localhost:6379/0");
  try {
    const job = buildWorkflowJob(input);
    await redis.xadd("workflow_jobs", "*", "payload", JSON.stringify(job));
  } finally {
    try {
      await redis.quit();
    } catch {
      // Cleanup failures are non-fatal: a successful xadd is durable, and an xadd
      // failure should propagate as the enqueue error.
    }
  }
}
