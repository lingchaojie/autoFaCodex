import { beforeEach, describe, expect, it, vi } from "vitest";
import { buildWorkflowJob, enqueueWorkflowJob } from "./queue";

const redisMock = vi.hoisted(() => ({
  Redis: vi.fn(),
  quit: vi.fn(),
  xadd: vi.fn()
}));

vi.mock("ioredis", () => ({
  default: redisMock.Redis
}));

beforeEach(() => {
  redisMock.Redis.mockReset();
  redisMock.quit.mockReset();
  redisMock.xadd.mockReset();
  redisMock.Redis.mockImplementation(function Redis() {
    return {
      quit: redisMock.quit,
      xadd: redisMock.xadd
    };
  });
});

describe("buildWorkflowJob", () => {
  it("creates a language-neutral pdf_to_ppt job payload", () => {
    const job = buildWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" });
    expect(job).toEqual({
      task_id: "task_1",
      workflow_type: "pdf_to_ppt"
    });
  });
});

describe("enqueueWorkflowJob", () => {
  it("adds workflow jobs to the Redis stream", async () => {
    const job = buildWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" });

    await enqueueWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" });

    expect(redisMock.xadd).toHaveBeenCalledWith(
      "workflow_jobs",
      "*",
      "payload",
      JSON.stringify(job)
    );
  });

  it("closes the Redis connection on success", async () => {
    await enqueueWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" });

    expect(redisMock.quit).toHaveBeenCalledTimes(1);
  });

  it("closes the Redis connection and propagates the original error when xadd rejects", async () => {
    const error = new Error("redis unavailable");
    redisMock.xadd.mockRejectedValueOnce(error);

    await expect(
      enqueueWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" })
    ).rejects.toBe(error);
    expect(redisMock.quit).toHaveBeenCalledTimes(1);
  });

  it("does not mask the original xadd error when closing the Redis connection also fails", async () => {
    const error = new Error("redis unavailable");
    redisMock.xadd.mockRejectedValueOnce(error);
    redisMock.quit.mockRejectedValueOnce(new Error("quit failed"));

    await expect(
      enqueueWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" })
    ).rejects.toBe(error);
  });

  it("does not reject when the job is enqueued but closing the Redis connection fails", async () => {
    redisMock.quit.mockRejectedValueOnce(new Error("quit failed"));

    await expect(
      enqueueWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" })
    ).resolves.toBeUndefined();
  });
});
