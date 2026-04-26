import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

export const pdfToPptWorkflowType = "pdf_to_ppt";
export const initialTaskStatus = "created";
export const queuedTaskStatus = "queued";

export function taskDir(taskId: string) {
  const root = process.env.SHARED_TASKS_DIR ?? "shared-tasks";
  return path.join(root, taskId);
}

export async function writeInputPdf(taskId: string, bytes: ArrayBuffer) {
  const dir = taskDir(taskId);
  await mkdir(dir, { recursive: true });
  const filePath = path.join(dir, "input.pdf");
  await writeFile(filePath, Buffer.from(bytes));
  return filePath;
}
