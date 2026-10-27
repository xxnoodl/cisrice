import { afterEach, expect, test, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App, loadHealth } from "./App";

const identity = {
  user: { id: "fixture-user", email: "fixture@example.test" },
  csrf_token: "fixture-csrf",
  expires_at: "2099-01-01T00:00:00Z",
};
function response(data: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => data };
}
function mockFetch({
  health = {
    status: "ok",
    dependencies: { postgresql: "ok", redis: "ok", schema: "ok" },
  },
  signedIn = false,
  offline = false,
  badLogin = false,
}: {
  health?: unknown;
  signedIn?: boolean;
  offline?: boolean;
  badLogin?: boolean;
} = {}) {
  let authenticated = signedIn;
  const requests = vi.fn(async (path: string, options?: RequestInit) => {
    if (path === "/api/auth/session")
      return response(
        authenticated ? identity : { detail: "Sign in required" },
        authenticated ? 200 : 401,
      );
    if (path === "/api/auth/status") return response({ setup_required: false });
    if (path === "/api/auth/login") {
      if (badLogin)
        return response({ detail: "Invalid email or password" }, 401);
      authenticated = true;
      return response(identity);
    }
    if (path === "/api/auth/logout") {
      authenticated = false;
      return response(null, 204);
    }
    if (path === "/api/workspaces" && options?.method === "POST")
      return response(
        { id: "workspace", name: "Portfolio", role: "owner" },
        201,
      );
    if (path === "/api/workspaces") return response([]);
    if (path === "/api/health/ready") {
      if (offline) throw new Error("offline");
      return response(
        health,
        (health as { status?: string })?.status === "degraded" ? 503 : 200,
      );
    }
    throw new Error("Unexpected API path: " + path);
  });
  vi.stubGlobal("fetch", requests);
  return requests;
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function mount(path = "/operations") {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("shows readiness and requires login for portfolio", async () => {
  mockFetch();
  mount();
  expect(await screen.findByText("System ok")).toBeInTheDocument();
  expect(screen.getByText("Portfolio")).toHaveAttribute(
    "aria-disabled",
    "true",
  );
});
test("operations route shows dependency degradation", async () => {
  mockFetch({
    health: { status: "degraded", dependencies: { redis: "unavailable" } },
  });
  mount();
  expect(await screen.findByText("System degraded")).toBeInTheDocument();
  expect(screen.getByText("unavailable")).toBeInTheDocument();
});
test("network failure is actionable", async () => {
  mockFetch({ offline: true });
  mount();
  expect(
    await screen.findByText(/API unavailable/, {}, { timeout: 3000 }),
  ).toBeInTheDocument();
});
test("rejects malformed service data", async () => {
  mockFetch({ health: { status: "ok", dependencies: null } });
  await expect(loadHealth()).rejects.toThrow("Invalid health response");
});
test("login enables portfolio and writes include the session CSRF token", async () => {
  const requests = mockFetch();
  mount("/");
  fireEvent.change(await screen.findByLabelText("Email"), {
    target: { value: "fixture@example.test" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "fixture-only-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  fireEvent.click(await screen.findByRole("link", { name: "Portfolio" }));
  fireEvent.change(await screen.findByLabelText("Workspace name"), {
    target: { value: "Portfolio" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));
  await waitFor(() =>
    expect(requests).toHaveBeenCalledWith(
      "/api/workspaces",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRF-Token": "fixture-csrf" }),
        body: JSON.stringify({ name: "Portfolio" }),
      }),
    ),
  );
});
test("login failures clear the password and show a generic server error", async () => {
  mockFetch({ badLogin: true });
  mount("/");
  fireEvent.change(await screen.findByLabelText("Email"), {
    target: { value: "fixture@example.test" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "fixture-only-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Invalid email or password",
  );
  expect(screen.getByLabelText("Password")).toHaveValue("");
});
test("signing out removes portfolio access", async () => {
  mockFetch({ signedIn: true });
  mount("/");
  fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  expect(
    await screen.findByRole("heading", { name: "Sign in to Cisrice" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Portfolio")).toHaveAttribute(
    "aria-disabled",
    "true",
  );
});
