import { fireEvent, render, screen } from "@testing-library/react";
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

  it("shows the typed password when the eye is pressed", async () => {
    await renderLoginPage();

    const password = screen.getByLabelText("密碼");
    expect(password).toHaveAttribute("type", "password");

    fireEvent.click(screen.getByRole("button", { name: "顯示密碼" }));
    expect(password).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "隱藏密碼" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "隱藏密碼" }));
    expect(password).toHaveAttribute("type", "password");
  });

  it("explains an expired login session", async () => {
    await renderLoginPage({ error: "session" });

    expect(screen.getByText("登入狀態已失效，請重新登入。")).toBeInTheDocument();
  });

  it("shows a Chinese message when credentials are wrong", async () => {
    await renderLoginPage({ error: "auth", detail: "LOGIN_BAD_CREDENTIALS" });

    expect(screen.getByText("帳號或密碼不正確，請再試一次。")).toBeInTheDocument();
    expect(screen.queryByText("LOGIN_BAD_CREDENTIALS")).not.toBeInTheDocument();
  });
});
