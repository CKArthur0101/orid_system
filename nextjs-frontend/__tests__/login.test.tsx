import { login } from "@/components/actions/login-action";
import { authJwtLogin } from "@/app/clientService";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

jest.mock("../app/clientService", () => ({
  authJwtLogin: jest.fn(),
}));

jest.mock("next/headers", () => {
  const mockSet = jest.fn();
  return { cookies: jest.fn().mockResolvedValue({ set: mockSet }) };
});

jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
}));

describe("login action", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should call login service action with the correct input", async () => {
    const formData = new FormData();
    formData.set("username", "a@a.com");
    formData.set("password", "Q12341414#");

    const mockSet = (await cookies()).set;

    (authJwtLogin as jest.Mock).mockResolvedValue({
      data: { access_token: "1245token" },
    });

    await login(formData);

    expect(authJwtLogin).toHaveBeenCalledWith({
      body: {
        username: "a@a.com",
        password: "Q12341414#",
      },
    });

    expect(cookies).toHaveBeenCalled();
    expect(mockSet).toHaveBeenCalledWith(
      "accessToken",
      "1245token",
      expect.objectContaining({
        httpOnly: true,
        maxAge: 43200,
        path: "/",
        sameSite: "lax",
        secure: false,
      }),
    );
    expect(redirect).toHaveBeenCalledWith("/home");
  });

  it("redirects when backend rejects credentials", async () => {
    const formData = new FormData();
    formData.set("username", "invalid@invalid.com");
    formData.set("password", "Q12341414#");

    (authJwtLogin as jest.Mock).mockResolvedValue({
      error: {
        detail: "LOGIN_BAD_CREDENTIALS",
      },
    });

    await login(formData);

    expect(authJwtLogin).toHaveBeenCalled();
    expect(redirect).toHaveBeenCalledWith(
      "/login?error=auth&detail=LOGIN_BAD_CREDENTIALS",
    );
    expect(cookies).not.toHaveBeenCalled();
  });

  it("redirects when username or password is missing", async () => {
    const formData = new FormData();
    formData.set("username", "");
    formData.set("password", "");

    await login(formData);

    expect(authJwtLogin).not.toHaveBeenCalled();
    expect(redirect).toHaveBeenCalledWith("/login?error=validation");
    expect(cookies).not.toHaveBeenCalled();
  });

  it("redirects on unexpected errors", async () => {
    (authJwtLogin as jest.Mock).mockRejectedValue(new Error("Network error"));

    const formData = new FormData();
    formData.append("username", "testuser");
    formData.append("password", "password123");

    await login(formData);

    expect(redirect).toHaveBeenCalledWith("/login?error=server");
  });
});
