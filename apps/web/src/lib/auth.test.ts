import { afterEach, describe, expect, test, vi } from "vitest";
import { cookies } from "next/headers";
import { createSession } from "./auth";

vi.mock("next/headers", () => ({
  cookies: vi.fn()
}));

const cookieStore = {
  set: vi.fn()
};

describe("createSession", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  test("sets a seven day http-only session cookie with production security", async () => {
    vi.stubEnv("SESSION_SECRET", "12345678901234567890123456789012");
    vi.stubEnv("NODE_ENV", "production");
    vi.mocked(cookies).mockResolvedValueOnce(cookieStore);

    await createSession("user_1");

    expect(cookieStore.set).toHaveBeenCalledWith(
      "autofacodex_session",
      expect.any(String),
      expect.objectContaining({
        httpOnly: true,
        maxAge: 60 * 60 * 24 * 7,
        path: "/",
        sameSite: "lax",
        secure: true
      })
    );
  });
});
