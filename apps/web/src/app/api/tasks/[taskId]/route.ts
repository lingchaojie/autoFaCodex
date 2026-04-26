import { NextResponse } from "next/server";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";

type RouteContext = {
  params: Promise<{ taskId: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { taskId } = await context.params;
  const task = await prisma.workflowTask.findFirst({
    where: { id: taskId, userId },
    include: {
      artifacts: true,
      events: { orderBy: { createdAt: "desc" }, take: 50 },
      messages: { orderBy: { createdAt: "asc" } }
    }
  });

  if (!task) return NextResponse.json({ error: "Not found" }, { status: 404 });

  return NextResponse.json({ task });
}
