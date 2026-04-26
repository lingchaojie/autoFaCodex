import { NextResponse } from "next/server";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { enqueueWorkflowJob } from "@/lib/queue";
import {
  initialTaskStatus,
  pdfToPptWorkflowType,
  queuedTaskStatus,
  writeInputPdf
} from "@/lib/tasks";

const pdfMagicBytes = new TextEncoder().encode("%PDF-");

function isPdf(bytes: ArrayBuffer) {
  const view = new Uint8Array(bytes);
  return pdfMagicBytes.every((byte, index) => view[index] === byte);
}

export async function GET() {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const tasks = await prisma.workflowTask.findMany({
    where: { userId },
    orderBy: { createdAt: "desc" }
  });

  return NextResponse.json({ tasks });
}

export async function POST(request: Request) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json({ error: "PDF file is required" }, { status: 400 });
  }

  const file = formData.get("file");
  if (!(file instanceof File) || file.type !== "application/pdf") {
    return NextResponse.json({ error: "PDF file is required" }, { status: 400 });
  }

  const bytes = await file.arrayBuffer();
  if (bytes.byteLength === 0 || !isPdf(bytes)) {
    return NextResponse.json({ error: "PDF file is required" }, { status: 400 });
  }

  const task = await prisma.workflowTask.create({
    data: {
      userId,
      workflowType: pdfToPptWorkflowType,
      status: initialTaskStatus,
      inputFilePath: ""
    }
  });

  try {
    const inputFilePath = await writeInputPdf(task.id, bytes);
    await prisma.workflowTask.update({
      where: { id: task.id },
      data: { inputFilePath }
    });
    await enqueueWorkflowJob({ taskId: task.id, workflowType: pdfToPptWorkflowType });
    await prisma.workflowTask.update({
      where: { id: task.id },
      data: { status: queuedTaskStatus }
    });
  } catch {
    try {
      await prisma.workflowTask.update({
        where: { id: task.id },
        data: { status: "failed" }
      });
    } catch {
      // Keep the upload endpoint response stable even if failure recording also fails.
    }
    return NextResponse.json({ error: "Failed to enqueue workflow" }, { status: 500 });
  }

  return NextResponse.json({ taskId: task.id });
}
