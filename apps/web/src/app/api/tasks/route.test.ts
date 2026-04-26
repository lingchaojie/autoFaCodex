import { beforeEach, describe, expect, test, vi } from "vitest";
import { GET, POST } from "./route";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { enqueueWorkflowJob } from "@/lib/queue";
import { writeInputPdf } from "@/lib/tasks";

vi.mock("@/lib/auth", () => ({
  getSessionUserId: vi.fn()
}));

vi.mock("@/lib/db", () => ({
  prisma: {
    workflowTask: {
      create: vi.fn(),
      findMany: vi.fn(),
      update: vi.fn()
    }
  }
}));

vi.mock("@/lib/queue", () => ({
  enqueueWorkflowJob: vi.fn()
}));

vi.mock("@/lib/tasks", () => ({
  initialTaskStatus: "created",
  pdfToPptWorkflowType: "pdf_to_ppt",
  queuedTaskStatus: "queued",
  writeInputPdf: vi.fn()
}));

const sessionUserId = vi.mocked(getSessionUserId);
const createTask = vi.mocked(prisma.workflowTask.create);
const findTasks = vi.mocked(prisma.workflowTask.findMany);
const updateTask = vi.mocked(prisma.workflowTask.update);
const enqueueJob = vi.mocked(enqueueWorkflowJob);
const writePdf = vi.mocked(writeInputPdf);

function multipartRequest(file: File) {
  const formData = new FormData();
  formData.set("file", file);
  return new Request("http://localhost/api/tasks", {
    method: "POST",
    body: formData
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

  test("POST returns 400 for malformed form data", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");

    const response = await POST(
      new Request("http://localhost/api/tasks", {
        method: "POST",
        body: "{"
      })
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "PDF file is required" });
    expect(createTask).not.toHaveBeenCalled();
  });

  test("POST returns 400 when a PDF file is not provided", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");

    const response = await POST(
      multipartRequest(new File(["not pdf"], "notes.txt", { type: "text/plain" }))
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "PDF file is required" });
    expect(createTask).not.toHaveBeenCalled();
  });

  test("POST returns 400 for an empty PDF upload before creating a task", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");

    const response = await POST(
      multipartRequest(new File([], "input.pdf", { type: "application/pdf" }))
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "PDF file is required" });
    expect(createTask).not.toHaveBeenCalled();
  });

  test("POST returns 400 when uploaded bytes are not a PDF before creating a task", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");

    const response = await POST(
      multipartRequest(new File(["not a pdf"], "input.pdf", { type: "application/pdf" }))
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "PDF file is required" });
    expect(createTask).not.toHaveBeenCalled();
  });

  test("POST stores a PDF upload, updates the task path, and enqueues the workflow", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");
    createTask.mockResolvedValueOnce({
      id: "task_1",
      userId: "user_1",
      workflowType: "pdf_to_ppt",
      status: "created",
      inputFilePath: "",
      outputFilePath: null,
      currentAttempt: 1,
      maxAttempts: 3,
      createdAt: new Date(),
      updatedAt: new Date()
    });
    updateTask.mockResolvedValueOnce({
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
    updateTask.mockResolvedValueOnce({
      id: "task_1",
      userId: "user_1",
      workflowType: "pdf_to_ppt",
      status: "queued",
      inputFilePath: "/shared/tasks/task_1/input.pdf",
      outputFilePath: null,
      currentAttempt: 1,
      maxAttempts: 3,
      createdAt: new Date(),
      updatedAt: new Date()
    });
    writePdf.mockResolvedValueOnce("/shared/tasks/task_1/input.pdf");

    const response = await POST(
      multipartRequest(new File(["%PDF-1.7"], "input.pdf", { type: "application/pdf" }))
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ taskId: "task_1" });
    expect(createTask).toHaveBeenCalledWith({
      data: {
        userId: "user_1",
        workflowType: "pdf_to_ppt",
        status: "created",
        inputFilePath: ""
      }
    });
    expect(writePdf).toHaveBeenCalledWith("task_1", expect.any(ArrayBuffer));
    expect(updateTask).toHaveBeenNthCalledWith(1, {
      where: { id: "task_1" },
      data: { inputFilePath: "/shared/tasks/task_1/input.pdf" }
    });
    expect(updateTask).toHaveBeenNthCalledWith(2, {
      where: { id: "task_1" },
      data: { status: "queued" }
    });
    expect(enqueueJob).toHaveBeenCalledWith({ taskId: "task_1", workflowType: "pdf_to_ppt" });
    expect(updateTask.mock.invocationCallOrder[1]).toBeLessThan(
      enqueueJob.mock.invocationCallOrder[0]
    );
  });

  test("POST marks the task failed and returns 500 when enqueue fails after queued status update", async () => {
    sessionUserId.mockResolvedValueOnce("user_1");
    createTask.mockResolvedValueOnce({
      id: "task_1",
      userId: "user_1",
      workflowType: "pdf_to_ppt",
      status: "created",
      inputFilePath: "",
      outputFilePath: null,
      currentAttempt: 1,
      maxAttempts: 3,
      createdAt: new Date(),
      updatedAt: new Date()
    });
    writePdf.mockResolvedValueOnce("/shared/tasks/task_1/input.pdf");
    enqueueJob.mockRejectedValueOnce(new Error("redis unavailable"));

    const response = await POST(
      multipartRequest(new File(["%PDF-1.7"], "input.pdf", { type: "application/pdf" }))
    );

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({ error: "Failed to enqueue workflow" });
    expect(updateTask).toHaveBeenNthCalledWith(1, {
      where: { id: "task_1" },
      data: { inputFilePath: "/shared/tasks/task_1/input.pdf" }
    });
    expect(updateTask).toHaveBeenNthCalledWith(2, {
      where: { id: "task_1" },
      data: { status: "queued" }
    });
    expect(updateTask.mock.invocationCallOrder[1]).toBeLessThan(
      enqueueJob.mock.invocationCallOrder[0]
    );
    expect(updateTask).toHaveBeenNthCalledWith(3, {
      where: { id: "task_1" },
      data: { status: "failed" }
    });
  });
});
