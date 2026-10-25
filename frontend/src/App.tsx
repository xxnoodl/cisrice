import { useQuery } from "@tanstack/react-query";
import { NavLink, Route, Routes } from "react-router-dom";

type Health = { status: string; dependencies: Record<string, string> };
export async function loadHealth(): Promise<Health> {
  const response = await fetch("/api/health/ready");
  if (!response.ok && response.status !== 503)
    throw new Error("Health request failed");
  const data: unknown = await response.json();
  if (
    !data ||
    typeof data !== "object" ||
    !("dependencies" in data) ||
    !("status" in data) ||
    typeof data.status !== "string" ||
    !data.dependencies ||
    typeof data.dependencies !== "object" ||
    Array.isArray(data.dependencies) ||
    Object.values(data.dependencies).some((value) => typeof value !== "string")
  )
    throw new Error("Invalid health response");
  return {
    status: data.status,
    dependencies: data.dependencies as Record<string, string>,
  };
}

function Operations() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: loadHealth,
    refetchInterval: 15000,
    retry: 1,
  });
  return (
    <section aria-labelledby="health-title">
      <h2 id="health-title">Service health</h2>
      <p role="status">
        {health.isPending
          ? "Checking services…"
          : health.isError
            ? "API unavailable. Check the backend and retry."
            : `System ${health.data.status}`}
      </p>
      {health.data && (
        <dl>
          {Object.entries(health.data.dependencies).map(([name, status]) => (
            <div key={name}>
              <dt>{name}</dt>
              <dd>{status}</dd>
            </div>
          ))}
        </dl>
      )}
      <button
        onClick={() => void health.refetch()}
        disabled={health.isFetching}
      >
        Refresh health
      </button>
      <p>
        Readiness checks PostgreSQL, Redis, and the database migration revision.
        Worker execution is not yet verified here.
      </p>
    </section>
  );
}

const planned = [
  "Portfolio",
  "Research",
  "Discovery",
  "Media Library",
  "Intelligence",
  "Production",
  "Review Queue",
  "Publishing",
  "Analytics",
  "Experiments",
  "Settings",
];
export function App() {
  return (
    <div className="layout">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <aside>
        <h1>Cisrice</h1>
        <p>Local content workspace</p>
        <nav aria-label="Main navigation">
          <NavLink to="/">Overview</NavLink>
          <NavLink to="/operations">Operations</NavLink>
          {planned.map((name) => (
            <span key={name} aria-disabled="true">
              {name} <small>Planned</small>
            </span>
          ))}
        </nav>
      </aside>
      <main id="main">
        <header>
          <p className="eyebrow">MILESTONE 0 · FOUNDATION</p>
          <h2>Your local production workspace</h2>
          <p>
            Research, media, production, and publishing will arrive in
            independently verified milestones.
          </p>
        </header>
        <Routes>
          <Route
            path="/"
            element={
              <>
                <section>
                  <h2>Foundation status</h2>
                  <p>
                    Portfolio setup and authentication are planned for Milestone
                    1. No external accounts are connected.
                  </p>
                </section>
                <Operations />
              </>
            }
          />
          <Route path="/operations" element={<Operations />} />
          <Route path="*" element={<h2>Page not found</h2>} />
        </Routes>
        <footer>
          Local-first · Human-controlled publishing · No paid AI dependency
        </footer>
      </main>
    </div>
  );
}
