import { NextResponse } from "next/server";
import { z } from "zod";

export function invalidRequestBody() {
  return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
}

export async function parseJsonBody<T>(request: Request, schema: z.ZodType<T>) {
  try {
    return { ok: true as const, data: schema.parse(await request.json()) };
  } catch (error) {
    if (error instanceof SyntaxError || error instanceof z.ZodError) {
      return { ok: false as const, response: invalidRequestBody() };
    }
    throw error;
  }
}

export function isPrismaUniqueConstraintError(error: unknown) {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    error.code === "P2002"
  );
}
