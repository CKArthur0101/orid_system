import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

import Page from "@/app/login/page";

async function renderLoginPage(searchParams: { error?: string; detail?: string } = {}) {
  render(await Page({ searchParams: Promise.resolve(searchParams) }));
}

describe("Login Page", () => {
  it("posts credentials to the same-origin login endpoint", async () => {
    await renderLoginPage();

    expect(screen.getByLabelText("帳號")).toBeInTheDocument();
    expect(screen.getByLabelText("密碼")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登入" })).toBeInTheDocument();
    const form = screen.getByRole("button", { name: "登入" }).closest("form");
    expect(form).toHaveAttribute("action", "/api/auth/login");
    expect(form).toHaveAttribute("method", "post");
  });

  it("explains an expired login session", async () => {
    await renderLoginPage({ error: "session" });

    expect(screen.getByText("登入狀態已失效，請重新登入。")).toBeInTheDocument();
  });

  it("shows the backend authentication detail", async () => {
    await renderLoginPage({ error: "auth", detail: "LOGIN_BAD_CREDENTIALS" });

    expect(screen.getByText("LOGIN_BAD_CREDENTIALS")).toBeInTheDocument();
  });
});
