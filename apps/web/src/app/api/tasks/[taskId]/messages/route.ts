import { NextResponse } from "next/server";
import { z } from "zod";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { parseJsonBody } from "@/lib/http";
import { enqueueWorkflowJob } from "@/lib/queue";
import { appendTaskConversationMessage, pdfToPptWorkflowType } from "@/lib/tasks";

const bodySchema = z.object({
  content: z.string().refine((content) => content.trim().length > 0)
});
const waitingUserReviewStatus = "waiting_user_review";
const runningRepairStatus = "running_repair";

type RouteContext = {
  params: Promise<{ taskId: string }>;
};

async function restoreWaitingUserReview(taskId: string) {
  try {
    await prisma.workflowTask.update({
      where: { id: taskId },
      data: { status: waitingUserReviewStatus }
    });
  } catch (error) {
    console.error("Failed to restore task repair status", error);
  }
}

export async function POST(request: Request, context: RouteContext) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const parsed = await parseJsonBody(request, bodySchema);
  if (!parsed.ok) return parsed.response;

  const { taskId } = await context.params;
  const task = await prisma.workflowTask.findFirst({
    where: { id: taskId, userId }
  });
  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });

  if (task.workflowType !== pdfToPptWorkflowType) {
    return NextResponse.json({ error: "Unsupported workflow type" }, { status: 400 });
  }
  if (task.status !== waitingUserReviewStatus) {
    return NextResponse.json({ error: "Task is not waiting for review" }, { status: 409 });
  }

  const claim = await prisma.workflowTask.updateMany({
    where: {
      id: taskId,
      userId,
      workflowType: pdfToPptWorkflowType,
      status: waitingUserReviewStatus
    },
    data: { status: runningRepairStatus }
  });
  if (claim.count !== 1) {
    return NextResponse.json({ error: "Task is not waiting for review" }, { status: 409 });
  }

  try {
    const message = await prisma.taskConversationMessage.create({
      data: {
        taskId,
        userId,
        role: "user",
        content: parsed.data.content
      }
    });
    await appendTaskConversationMessage(taskId, {
      role: message.role,
      content: message.content,
      createdAt: message.createdAt
    });
    await enqueueWorkflowJob({
      taskId,
      workflowType: pdfToPptWorkflowType,
      mode: "repair"
    });
  } catch (error) {
    console.error("Failed to process repair workflow request", error);
    await restoreWaitingUserReview(taskId);
    return NextResponse.json({ error: "Failed to enqueue workflow" }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
