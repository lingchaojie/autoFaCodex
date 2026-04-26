import { NextResponse } from "next/server";
import { z } from "zod";
import { createSession, hashPassword } from "@/lib/auth";
import { prisma } from "@/lib/db";

const bodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(8)
});

export async function POST(request: Request) {
  const body = bodySchema.parse(await request.json());
  const user = await prisma.user.create({
    data: { email: body.email.toLowerCase(), passwordHash: await hashPassword(body.password) }
  });
  await createSession(user.id);
  return NextResponse.json({ userId: user.id });
}
