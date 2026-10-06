/** @jest-environment node */

import { NextRequest } from "next/server";

import { proxy } from "@/proxy";

describe("authentication proxy redirects", () => {
  it("uses the public forwarded origin instead of the internal container address", async () => {
    const request = new NextRequest("http://0.0.0.0:3000/home", {
      headers: {
        Host: "0.0.0.0:3000",
        "X-Forwarded-Host": "app.dioridwriting.com",
        "X-Forwarded-Proto": "https",
      },
    });

    const response = await proxy(request);

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://app.dioridwriting.com/login");
  });
});
