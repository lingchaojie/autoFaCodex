import { NextResponse } from "next/server";
import { z } from "zod";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { parseJsonBody } from "@/lib/http";
import { initialTaskStatus, pdfToPptWorkflowType } from "@/lib/tasks";

const bodySchema = z.object({
  inputFilePath: z.string().min(1)
});

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

  const parsed = await parseJsonBody(request, bodySchema);
  if (!parsed.ok) return parsed.response;

  const body = parsed.data;
  const task = await prisma.workflowTask.create({
    data: {
      userId,
      workflowType: pdfToPptWorkflowType,
      status: initialTaskStatus,
      inputFilePath: body.inputFilePath
    }
  });

  return NextResponse.json({ taskId: task.id });
}
