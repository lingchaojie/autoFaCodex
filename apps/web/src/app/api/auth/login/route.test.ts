import { beforeEach, describe, expect, test, vi } from "vitest";
import { POST } from "./route";
import { createSession, verifyPassword } from "@/lib/auth";
import { prisma } from "@/lib/db";

vi.mock("@/lib/auth", () => ({
  createSession: vi.fn(),
  verifyPassword: vi.fn()
}));

vi.mock("@/lib/db", () => ({
  prisma: {
    user: {
      findUnique: vi.fn()
    }
  }
}));

const findUser = vi.mocked(prisma.user.findUnique);
const checkPassword = vi.mocked(verifyPassword);

function jsonRequest(body: unknown) {
  return new Request("http://localhost/api/auth/login", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

describe("POST /api/auth/login", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns 400 for invalid JSON", async () => {
    const response = await POST(
      new Request("http://localhost/api/auth/login", {
        method: "POST",
        body: "{"
      })
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "Invalid request body" });
    expect(findUser).not.toHaveBeenCalled();
  });

  test("returns 400 for invalid login body", async () => {
    const response = await POST(jsonRequest({ email: "not-email", password: "" }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "Invalid request body" });
    expect(findUser).not.toHaveBeenCalled();
  });

  test("returns generic 401 for invalid credentials", async () => {
    findUser.mockResolvedValueOnce(null);

    const response = await POST(jsonRequest({ email: "USER@example.com", password: "wrong" }));

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: "Invalid credentials" });
    expect(findUser).toHaveBeenCalledWith({ where: { email: "user@example.com" } });
    expect(createSession).not.toHaveBeenCalled();
  });

  test("creates a session for valid credentials", async () => {
    findUser.mockResolvedValueOnce({
      id: "user_1",
      email: "user@example.com",
      passwordHash: "hashed-password",
      createdAt: new Date()
    });
    checkPassword.mockResolvedValueOnce(true);

    const response = await POST(jsonRequest({ email: "USER@example.com", password: "password123" }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ userId: "user_1" });
    expect(createSession).toHaveBeenCalledWith("user_1");
  });
});
