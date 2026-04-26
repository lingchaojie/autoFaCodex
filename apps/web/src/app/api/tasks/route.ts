import { NextResponse } from "next/server";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { enqueueWorkflowJob } from "@/lib/queue";
import { pdfToPptWorkflowType, queuedTaskStatus, writeInputPdf } from "@/lib/tasks";

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

  const task = await prisma.workflowTask.create({
    data: {
      userId,
      workflowType: pdfToPptWorkflowType,
      status: queuedTaskStatus,
      inputFilePath: ""
    }
  });

  const inputFilePath = await writeInputPdf(task.id, await file.arrayBuffer());
  await prisma.workflowTask.update({
    where: { id: task.id },
    data: { inputFilePath }
  });
  await enqueueWorkflowJob({ taskId: task.id, workflowType: pdfToPptWorkflowType });

  return NextResponse.json({ taskId: task.id });
}
