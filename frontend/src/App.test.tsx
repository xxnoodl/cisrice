import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App, loadHealth } from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function mount(path = "/") {
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
test("shows real readiness and labels planned functionality", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "ok",
        dependencies: { postgresql: "ok", redis: "ok", schema: "ok" },
      }),
    }),
  );
  mount();
  expect(await screen.findByText("System ok")).toBeInTheDocument();
  expect(screen.getByText("Portfolio")).toHaveAttribute(
    "aria-disabled",
    "true",
  );
});
test("operations route shows dependency degradation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({
        status: "degraded",
        dependencies: { redis: "unavailable" },
      }),
    }),
  );
  mount("/operations");
  expect(await screen.findByText("System degraded")).toBeInTheDocument();
  expect(screen.getByText("unavailable")).toBeInTheDocument();
});
test("network failure is actionable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  mount();
  expect(
    await screen.findByText(/API unavailable/, {}, { timeout: 3000 }),
  ).toBeInTheDocument();
});
test("rejects malformed service data", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", dependencies: null }),
    }),
  );
  await expect(loadHealth()).rejects.toThrow("Invalid health response");
});
