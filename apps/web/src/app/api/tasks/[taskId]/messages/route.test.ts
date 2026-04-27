import { beforeEach, describe, expect, test, vi } from "vitest";
import { POST } from "./route";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { enqueueWorkflowJob } from "@/lib/queue";
import { appendTaskConversationMessage } from "@/lib/tasks";

vi.mock("@/lib/auth", () => ({
  getSessionUserId: vi.fn()
}));

vi.mock("@/lib/db", () => ({
  prisma: {
    workflowTask: {
      findFirst: vi.fn(),
      updateMany: vi.fn(),
      update: vi.fn()
    },
    taskConversationMessage: {
      create: vi.fn()
    }
  }
}));

vi.mock("@/lib/queue", () => ({
  enqueueWorkflowJob: vi.fn()
}));

vi.mock("@/lib/tasks", () => ({
  appendTaskConversationMessage: vi.fn(),
  pdfToPptWorkflowType: "pdf_to_ppt"
}));

const sessionUserId = vi.mocked(getSessionUserId);
const findTask = vi.mocked(prisma.workflowTask.findFirst);
const claimTask = vi.mocked(prisma.workflowTask.updateMany);
const updateTask = vi.mocked(prisma.workflowTask.update);
const createMessage = vi.mocked(prisma.taskConversationMessage.create);
const appendMessage = vi.mocked(appendTaskConversationMessage);
const enqueueJob = vi.mocked(enqueueWorkflowJob);

function jsonRequest(body: unknown) {
  return new Request("http://localhost/api/tasks/task_1/messages", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

function routeContext(taskId = "task_1") {
  return { params: Promise.resolve({ taskId }) };
}

function repairableTask(overrides: Record<string, unknown> = {}) {
  return {
    id: "task_1",
    userId: "user_1",
    workflowType: "pdf_to_ppt",
    status: "waiting_user_review",
    inputFilePath: "/shared/tasks/task_1/input.pdf",
    outputFilePath: "/shared/tasks/task_1/output/candidate.v1.pptx",
    currentAttempt: 1,
    maxAttempts: 3,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides
  };
}

describe("POST /api/tasks/[taskId]/messages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    claimTask.mockResolvedValue({ count: 1 });
    createMessage.mockResolvedValue({
      id: "msg_1",
      taskId: "task_1",
      userId: "user_1",
      role: "user",
      content: "Please fix slide 2.",
      createdAt: new Date("2026-04-26T12:00:00.000Z")
    });
  });

  test("returns 401 without a session", async () => {
    sessionUserId.mockResolvedValueOnce(null);

    const response = await POST(jsonRequest({ content: "Please fix slide 2." }), routeContext());

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: "Unauthorized" });
    expect(findTask).not.toHaveBeenCalled();
  });

  test("returns 400 for invalid message content", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");

    const response = await POST(jsonRequest({ content: "   " }), routeContext());

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "Invalid request body" });
    expect(findTask).not.toHaveBeenCalled();
  });

  test("returns 404 when the task does not belong to the user", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(null);

    const response = await POST(jsonRequest({ content: "Please fix slide 2." }), routeContext());

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({ error: "Task not found" });
    expect(findTask).toHaveBeenCalledWith({
      where: { id: "task_1", userId: "user_1" }
    });
    expect(createMessage).not.toHaveBeenCalled();
  });

  test("returns 400 for unsupported workflow type without claiming repair", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(repairableTask({ workflowType: "other_workflow" }));

    const response = await POST(jsonRequest({ content: "Please fix slide 2." }), routeContext());

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "Unsupported workflow type" });
    expect(claimTask).not.toHaveBeenCalled();
    expect(updateTask).not.toHaveBeenCalled();
    expect(createMessage).not.toHaveBeenCalled();
    expect(appendMessage).not.toHaveBeenCalled();
    expect(enqueueJob).not.toHaveBeenCalled();
  });

  test("returns 409 for non-repairable task status without claiming repair", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(repairableTask({ status: "running_repair" }));

    const response = await POST(jsonRequest({ content: "Please fix slide 2." }), routeContext());

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toEqual({ error: "Task is not waiting for review" });
    expect(claimTask).not.toHaveBeenCalled();
    expect(updateTask).not.toHaveBeenCalled();
    expect(createMessage).not.toHaveBeenCalled();
    expect(appendMessage).not.toHaveBeenCalled();
    expect(enqueueJob).not.toHaveBeenCalled();
  });

  test("returns 409 when the conditional repair claim does not update a task", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(repairableTask());
    claimTask.mockResolvedValueOnce({ count: 0 });

    const response = await POST(jsonRequest({ content: "Please fix slide 2." }), routeContext());

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toEqual({ error: "Task is not waiting for review" });
    expect(claimTask).toHaveBeenCalledWith({
      where: {
        id: "task_1",
        userId: "user_1",
        workflowType: "pdf_to_ppt",
        status: "waiting_user_review"
      },
      data: { status: "running_repair" }
    });
    expect(updateTask).not.toHaveBeenCalled();
    expect(createMessage).not.toHaveBeenCalled();
    expect(appendMessage).not.toHaveBeenCalled();
    expect(enqueueJob).not.toHaveBeenCalled();
  });

  test("restores waiting review status and returns 500 when appending the message fails", async () => {
    const createdAt = new Date("2026-04-26T12:00:00.000Z");
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(repairableTask());
    claimTask.mockResolvedValueOnce({ count: 1 });
    createMessage.mockResolvedValueOnce({
      id: "msg_1",
      taskId: "task_1",
      userId: "user_1",
      role: "user",
      content: "Please fix slide 2.",
      createdAt
    });
    appendMessage.mockRejectedValueOnce(new Error("shared directory unavailable"));

    const response = await POST(jsonRequest({ content: "Please fix slide 2." }), routeContext());

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({ error: "Failed to enqueue workflow" });
    expect(updateTask).toHaveBeenCalledWith({
      where: { id: "task_1" },
      data: { status: "waiting_user_review" }
    });
    expect(enqueueJob).not.toHaveBeenCalled();
  });

  test("restores waiting review status and returns 500 when creating the message fails", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(repairableTask());
    claimTask.mockResolvedValueOnce({ count: 1 });
    createMessage.mockRejectedValueOnce(new Error("database unavailable"));

    const response = await POST(jsonRequest({ content: "Please fix slide 2." }), routeContext());

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({ error: "Failed to enqueue workflow" });
    expect(updateTask).toHaveBeenCalledWith({
      where: { id: "task_1" },
      data: { status: "waiting_user_review" }
    });
    expect(appendMessage).not.toHaveBeenCalled();
    expect(enqueueJob).not.toHaveBeenCalled();
  });

  test("restores waiting review status and returns 500 when enqueue fails", async () => {
    const createdAt = new Date("2026-04-26T12:00:00.000Z");
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(repairableTask());
    claimTask.mockResolvedValueOnce({ count: 1 });
    createMessage.mockResolvedValueOnce({
      id: "msg_1",
      taskId: "task_1",
      userId: "user_1",
      role: "user",
      content: "Please fix slide 2.",
      createdAt
    });
    enqueueJob.mockRejectedValueOnce(new Error("redis unavailable"));

    const response = await POST(jsonRequest({ content: "Please fix slide 2." }), routeContext());

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({ error: "Failed to enqueue workflow" });
    expect(updateTask).toHaveBeenCalledWith({
      where: { id: "task_1" },
      data: { status: "waiting_user_review" }
    });
  });

  test("claims the repair before storing the user message and enqueuing a repair job", async () => {
    const createdAt = new Date("2026-04-26T12:00:00.000Z");
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(repairableTask());
    claimTask.mockResolvedValueOnce({ count: 1 });
    createMessage.mockResolvedValueOnce({
      id: "msg_1",
      taskId: "task_1",
      userId: "user_1",
      role: "user",
      content: " Please fix slide 2. ",
      createdAt
    });

    const response = await POST(
      jsonRequest({ content: " Please fix slide 2. " }),
      routeContext()
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true });
    expect(createMessage).toHaveBeenCalledWith({
      data: {
        taskId: "task_1",
        userId: "user_1",
        role: "user",
        content: " Please fix slide 2. "
      }
    });
    expect(claimTask).toHaveBeenCalledWith({
      where: {
        id: "task_1",
        userId: "user_1",
        workflowType: "pdf_to_ppt",
        status: "waiting_user_review"
      },
      data: { status: "running_repair" }
    });
    expect(appendMessage).toHaveBeenCalledWith("task_1", {
      role: "user",
      content: " Please fix slide 2. ",
      createdAt
    });
    expect(updateTask).not.toHaveBeenCalled();
    expect(enqueueJob).toHaveBeenCalledWith({
      taskId: "task_1",
      workflowType: "pdf_to_ppt",
      mode: "repair"
    });
    expect(claimTask.mock.invocationCallOrder[0]).toBeLessThan(
      createMessage.mock.invocationCallOrder[0]
    );
    expect(createMessage.mock.invocationCallOrder[0]).toBeLessThan(
      appendMessage.mock.invocationCallOrder[0]
    );
    expect(appendMessage.mock.invocationCallOrder[0]).toBeLessThan(
      enqueueJob.mock.invocationCallOrder[0]
    );
  });
});
