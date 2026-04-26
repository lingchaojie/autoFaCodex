import { access, mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { appendTaskConversationMessage, taskDir, writeInputPdf } from "./tasks";

let sharedTasksDir: string;
let previousSharedTasksDir: string | undefined;

describe("task shared directory helpers", () => {
  beforeEach(async () => {
    previousSharedTasksDir = process.env.SHARED_TASKS_DIR;
    sharedTasksDir = await mkdtemp(path.join(tmpdir(), "autofacodex-tasks-"));
    process.env.SHARED_TASKS_DIR = sharedTasksDir;
  });

  afterEach(async () => {
    if (previousSharedTasksDir === undefined) {
      delete process.env.SHARED_TASKS_DIR;
    } else {
      process.env.SHARED_TASKS_DIR = previousSharedTasksDir;
    }
    await rm(sharedTasksDir, { recursive: true, force: true });
  });

  test("writeInputPdf stores input.pdf in the shared task directory", async () => {
    const filePath = await writeInputPdf("task_1", new TextEncoder().encode("%PDF-1.7").buffer);

    expect(filePath).toBe(path.join(sharedTasksDir, "task_1", "input.pdf"));
    const fileStat = await stat(filePath);
    expect(fileStat.isFile()).toBe(true);
    await expect(readFile(filePath, "utf8")).resolves.toBe("%PDF-1.7");
  });

  test("appendTaskConversationMessage appends JSONL conversation records", async () => {
    const firstCreatedAt = new Date("2026-04-26T12:00:00.000Z");
    const secondCreatedAt = new Date("2026-04-26T12:01:00.000Z");

    const filePath = await appendTaskConversationMessage("task_1", {
      role: "user",
      content: "Please fix slide 2.",
      createdAt: firstCreatedAt
    });
    await appendTaskConversationMessage("task_1", {
      role: "assistant",
      content: "Repair queued.",
      createdAt: secondCreatedAt
    });

    expect(filePath).toBe(path.join(taskDir("task_1"), "conversation", "messages.jsonl"));
    const lines = (await readFile(filePath, "utf8")).trimEnd().split("\n");
    expect(lines.map((line) => JSON.parse(line))).toEqual([
      {
        role: "user",
        content: "Please fix slide 2.",
        createdAt: "2026-04-26T12:00:00.000Z"
      },
      {
        role: "assistant",
        content: "Repair queued.",
        createdAt: "2026-04-26T12:01:00.000Z"
      }
    ]);
  });

  test("taskDir rejects traversal task ids before writing outside the shared root", async () => {
    const outsidePath = path.join(sharedTasksDir, "..", "escape");

    expect(() => taskDir("../escape")).toThrow("Invalid task id");
    await expect(
      appendTaskConversationMessage("../escape", {
        role: "user",
        content: "This should not be written."
      })
    ).rejects.toThrow("Invalid task id");
    await expect(access(outsidePath)).rejects.toThrow();
  });
});
