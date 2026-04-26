import { beforeEach, describe, expect, test, vi } from "vitest";
import { POST } from "./route";
import { createSession, hashPassword } from "@/lib/auth";
import { prisma } from "@/lib/db";

vi.mock("@/lib/auth", () => ({
  createSession: vi.fn(),
  hashPassword: vi.fn(async () => "hashed-password")
}));

vi.mock("@/lib/db", () => ({
  prisma: {
    user: {
      create: vi.fn()
    }
  }
}));

const createUser = vi.mocked(prisma.user.create);

function jsonRequest(body: unknown) {
  return new Request("http://localhost/api/auth/register", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

describe("POST /api/auth/register", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns 400 for invalid JSON", async () => {
    const response = await POST(
      new Request("http://localhost/api/auth/register", {
        method: "POST",
        body: "{"
      })
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "Invalid request body" });
    expect(createUser).not.toHaveBeenCalled();
  });

  test("returns 400 for invalid registration body", async () => {
    const response = await POST(jsonRequest({ email: "not-email", password: "short" }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "Invalid request body" });
    expect(createUser).not.toHaveBeenCalled();
  });

  test("returns 409 for duplicate email", async () => {
    createUser.mockRejectedValueOnce(Object.assign(new Error("Unique constraint failed"), { code: "P2002" }));

    const response = await POST(jsonRequest({ email: "USER@example.com", password: "password123" }));

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toEqual({ error: "Email already registered" });
    expect(hashPassword).toHaveBeenCalledWith("password123");
    expect(createSession).not.toHaveBeenCalled();
  });

  test("creates a user and session for valid registration", async () => {
    createUser.mockResolvedValueOnce({
      id: "user_1",
      email: "user@example.com",
      passwordHash: "hashed-password",
      createdAt: new Date()
    });

    const response = await POST(jsonRequest({ email: "USER@example.com", password: "password123" }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ userId: "user_1" });
    expect(createUser).toHaveBeenCalledWith({
      data: { email: "user@example.com", passwordHash: "hashed-password" }
    });
    expect(createSession).toHaveBeenCalledWith("user_1");
  });
});
