import { NextResponse } from "next/server";
import { z } from "zod";
import { createSession, hashPassword } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { isPrismaUniqueConstraintError, parseJsonBody } from "@/lib/http";

const bodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(8)
});

export async function POST(request: Request) {
  const parsed = await parseJsonBody(request, bodySchema);
  if (!parsed.ok) return parsed.response;

  const body = parsed.data;
  let user;
  try {
    user = await prisma.user.create({
      data: { email: body.email.toLowerCase(), passwordHash: await hashPassword(body.password) }
    });
  } catch (error) {
    if (isPrismaUniqueConstraintError(error)) {
      return NextResponse.json({ error: "Email already registered" }, { status: 409 });
    }
    throw error;
  }
  await createSession(user.id);
  return NextResponse.json({ userId: user.id });
}
