import { beforeEach, describe, expect, test, vi } from "vitest";
import { GET } from "./route";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";

vi.mock("@/lib/auth", () => ({
  getSessionUserId: vi.fn()
}));

vi.mock("@/lib/db", () => ({
  prisma: {
    workflowTask: {
      findFirst: vi.fn()
    }
  }
}));

const sessionUserId = vi.mocked(getSessionUserId);
const findTask = vi.mocked(prisma.workflowTask.findFirst);

function routeContext(taskId = "task_1") {
  return { params: Promise.resolve({ taskId }) };
}

function taskDetail() {
  return {
    id: "task_1",
    userId: "user_1",
    workflowType: "pdf_to_ppt",
    status: "waiting_user_review",
    inputFilePath: "/shared/tasks/task_1/input.pdf",
    outputFilePath: "/shared/tasks/task_1/output/candidate.v1.pptx",
    currentAttempt: 1,
    maxAttempts: 3,
    createdAt: new Date("2026-04-26T12:00:00.000Z"),
    updatedAt: new Date("2026-04-26T12:05:00.000Z"),
    artifacts: [
      {
        id: "artifact_1",
        taskId: "task_1",
        artifactType: "validator_report",
        path: "/shared/tasks/task_1/report.json",
        metadata: { score: 0.82 },
        createdAt: new Date("2026-04-26T12:04:00.000Z")
      }
    ],
    events: [
      {
        id: "event_1",
        taskId: "task_1",
        role: "validator",
        eventType: "validation_completed",
        message: "Validator report written",
        payload: { score: 0.82 },
        createdAt: new Date("2026-04-26T12:04:00.000Z")
      }
    ],
    messages: [
      {
        id: "message_1",
        taskId: "task_1",
        userId: "user_1",
        role: "user",
        content: "Please make slide 2 easier to edit.",
        createdAt: new Date("2026-04-26T12:06:00.000Z")
      }
    ]
  };
}

describe("GET /api/tasks/[taskId]", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns 401 without a session", async () => {
    sessionUserId.mockResolvedValueOnce(null);

    const response = await GET(new Request("http://localhost/api/tasks/task_1"), routeContext());

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: "Unauthorized" });
    expect(findTask).not.toHaveBeenCalled();
  });

  test("returns 404 when the task does not belong to the user", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(null);

    const response = await GET(new Request("http://localhost/api/tasks/task_1"), routeContext());

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({ error: "Not found" });
    expect(findTask).toHaveBeenCalledWith({
      where: { id: "task_1", userId: "user_1" },
      include: {
        artifacts: true,
        events: { orderBy: { createdAt: "desc" }, take: 50 },
        messages: { orderBy: { createdAt: "asc" } }
      }
    });
  });

  test("returns the task with artifacts, recent events, and conversation messages", async () => {
    const task = taskDetail();
    sessionUserId.mockResolvedValueOnce("user_1");
    findTask.mockResolvedValueOnce(task);

    const response = await GET(new Request("http://localhost/api/tasks/task_1"), routeContext());

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual(JSON.parse(JSON.stringify({ task })));
    expect(findTask).toHaveBeenCalledWith({
      where: { id: "task_1", userId: "user_1" },
      include: {
        artifacts: true,
        events: { orderBy: { createdAt: "desc" }, take: 50 },
        messages: { orderBy: { createdAt: "asc" } }
      }
    });
  });
});
