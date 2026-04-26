import { beforeEach, describe, expect, test, vi } from "vitest";
import { GET, POST } from "./route";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";

vi.mock("@/lib/auth", () => ({
  getSessionUserId: vi.fn()
}));

vi.mock("@/lib/db", () => ({
  prisma: {
    workflowTask: {
      create: vi.fn(),
      findMany: vi.fn()
    }
  }
}));

const sessionUserId = vi.mocked(getSessionUserId);
const createTask = vi.mocked(prisma.workflowTask.create);
const findTasks = vi.mocked(prisma.workflowTask.findMany);

function jsonRequest(body: unknown) {
  return new Request("http://localhost/api/tasks", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

describe("/api/tasks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("GET returns 401 without a session", async () => {
    sessionUserId.mockResolvedValueOnce(null);

    const response = await GET();

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: "Unauthorized" });
    expect(findTasks).not.toHaveBeenCalled();
  });

  test("POST returns 400 for invalid JSON", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");

    const response = await POST(
      new Request("http://localhost/api/tasks", {
        method: "POST",
        body: "{"
      })
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "Invalid request body" });
    expect(createTask).not.toHaveBeenCalled();
  });

  test("POST returns 400 for invalid task body", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");

    const response = await POST(jsonRequest({ inputFilePath: "" }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "Invalid request body" });
    expect(createTask).not.toHaveBeenCalled();
  });

  test("POST creates a task record for valid input", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");
    createTask.mockResolvedValueOnce({
      id: "task_1",
      userId: "user_1",
      workflowType: "pdf_to_ppt",
      status: "created",
      inputFilePath: "/shared/tasks/task_1/input.pdf",
      outputFilePath: null,
      currentAttempt: 1,
      maxAttempts: 3,
      createdAt: new Date(),
      updatedAt: new Date()
    });

    const response = await POST(jsonRequest({ inputFilePath: "/shared/tasks/task_1/input.pdf" }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ taskId: "task_1" });
    expect(createTask).toHaveBeenCalledWith({
      data: {
        userId: "user_1",
        workflowType: "pdf_to_ppt",
        status: "created",
        inputFilePath: "/shared/tasks/task_1/input.pdf"
      }
    });
  });
});
