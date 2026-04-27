import { appendFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

export const pdfToPptWorkflowType = "pdf_to_ppt";
export const initialTaskStatus = "created";
export const queuedTaskStatus = "queued";

export function taskDir(taskId: string) {
  const root = process.env.SHARED_TASKS_DIR ?? "shared-tasks";
  const rootPath = path.resolve(root);
  const targetPath = path.resolve(rootPath, taskId);
  const relativePath = path.relative(rootPath, targetPath);
  if (
    relativePath.length === 0 ||
    relativePath.startsWith("..") ||
    path.isAbsolute(relativePath)
  ) {
    throw new Error("Invalid task id");
  }
  return path.join(root, relativePath);
}

export async function writeInputPdf(taskId: string, bytes: ArrayBuffer) {
  const dir = taskDir(taskId);
  await mkdir(dir, { recursive: true });
  const filePath = path.join(dir, "input.pdf");
  await writeFile(filePath, Buffer.from(bytes));
  return filePath;
}

export type TaskConversationMessageInput = {
  role: string;
  content: string;
  createdAt?: Date | string;
};

export async function appendTaskConversationMessage(
  taskId: string,
  message: TaskConversationMessageInput
) {
  const conversationDir = path.join(taskDir(taskId), "conversation");
  await mkdir(conversationDir, { recursive: true });
  const filePath = path.join(conversationDir, "messages.jsonl");
  const createdAt =
    message.createdAt instanceof Date
      ? message.createdAt.toISOString()
      : message.createdAt ?? new Date().toISOString();
  await appendFile(
    filePath,
    `${JSON.stringify({ role: message.role, content: message.content, createdAt })}\n`,
    "utf8"
  );
  return filePath;
}
