import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Route, Routes, useSearchParams } from "react-router-dom";
import { api, session, type Workspace, type Niche, type Brand } from "./api";
import { LoginForm } from "./Auth";
import { Portfolio } from "./Portfolio";
import { Discovery } from "./Discovery";

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
  "Media Library",
  "Intelligence",
  "Production",
  "Review Queue",
  "Publishing",
  "Analytics",
  "Experiments",
];

export function App() {
  const client = useQueryClient();
  const [search, setSearch] = useSearchParams();
  const auth = useQuery({
    queryKey: ["session"],
    queryFn: session,
    retry: false,
    refetchInterval: 60000,
  });
  const user = auth.data;
  const workspaces = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => api<Workspace[]>("/workspaces"),
    enabled: !!user,
  });
  const workspace =
    workspaces.data?.find((row) => row.id === search.get("workspace")) ??
    workspaces.data?.[0];
  const root = workspace ? "/workspaces/" + workspace.id : "";
  const niches = useQuery({
    queryKey: ["niches", root],
    queryFn: () => api<Niche[]>(root + "/niches"),
    enabled: !!user && !!root,
  });
  const brands = useQuery({
    queryKey: ["brands", root],
    queryFn: () => api<Brand[]>(root + "/brands"),
    enabled: !!user && !!root,
  });
  const filtered =
    brands.data?.filter(
      (row) => !search.get("niche") || row.niche_id === search.get("niche"),
    ) ?? [];
  const brand =
    filtered.find((row) => row.id === search.get("brand")) ?? filtered[0];
  const logout = useMutation({
    mutationFn: () =>
      api<void>("/auth/logout", "POST", undefined, user?.csrf_token),
    onSuccess: () => {
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(["session"], null);
      setSearch({});
    },
  });
  function select(w: string, n?: string, b?: string) {
    setSearch({
      workspace: w,
      ...(n ? { niche: n } : {}),
      ...(b ? { brand: b } : {}),
    });
  }
  const portfolio = user ? (
    <Portfolio
      session={user}
      workspaces={workspaces.data ?? []}
      workspace={workspace}
      niches={niches.data ?? []}
      brands={brands.data ?? []}
      brand={brand}
      select={select}
    />
  ) : (
    <LoginForm />
  );
  const error = workspaces.error ?? niches.error ?? brands.error;
  return (
    <div className="layout">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <aside>
        <h1>Cisrice</h1>
        <p>Local content workspace</p>
        <nav aria-label="Main navigation">
          <NavLink to={{ pathname: "/", search: search.toString() }}>
            Overview
          </NavLink>
          {user ? (
            <NavLink to={{ pathname: "/portfolio", search: search.toString() }}>
              Portfolio
            </NavLink>
          ) : (
            <span aria-disabled="true">
              Portfolio <small>Sign in</small>
            </span>
          )}
          <NavLink to={{ pathname: "/operations", search: search.toString() }}>
            Operations
          </NavLink>
          {user &&
            ["Discovery", "Research"].map((name) => (
              <NavLink
                key={name}
                to={{
                  pathname: "/" + name.toLowerCase(),
                  search: search.toString(),
                }}
              >
                {name}
              </NavLink>
            ))}
          {user ? (
            <NavLink to={{ pathname: "/settings", search: search.toString() }}>
              Settings
            </NavLink>
          ) : (
            <span aria-disabled="true">
              Settings <small>Sign in</small>
            </span>
          )}
          {planned.map((name) => (
            <span key={name} aria-disabled="true">
              {name} <small>Planned</small>
            </span>
          ))}
        </nav>
        {user && (
          <div className="identity">
            <p>{user.user.email}</p>
            <button
              className="secondary"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
            >
              Sign out
            </button>
            {logout.error && <p role="alert">{logout.error.message}</p>}
          </div>
        )}
      </aside>
      <main id="main">
        <header>
          <p className="eyebrow">MILESTONE 2 · DISCOVERY & RESEARCH</p>
          <h2>Your local production workspace</h2>
          {user && (
            <div className="context" aria-label="Portfolio context">
              <label>
                Workspace
                <select
                  value={workspace?.id ?? ""}
                  onChange={(e) => select(e.target.value)}
                >
                  <option value="" disabled>
                    Select workspace
                  </option>
                  {workspaces.data?.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Niche filter
                <select
                  value={search.get("niche") ?? ""}
                  onChange={(e) => select(workspace?.id ?? "", e.target.value)}
                >
                  <option value="">All niches</option>
                  {niches.data?.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Brand
                <select
                  value={brand?.id ?? ""}
                  onChange={(e) =>
                    select(
                      workspace?.id ?? "",
                      search.get("niche") ?? undefined,
                      e.target.value,
                    )
                  }
                >
                  <option value="" disabled>
                    Select brand
                  </option>
                  {filtered.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
        </header>
        {auth.error && (
          <p role="alert">
            Could not check your session. Check service health and reload.
          </p>
        )}
        {error && <p role="alert">{error.message}</p>}
        {auth.isPending ? (
          <p role="status">Checking session…</p>
        ) : (
          <Routes>
            <Route
              path="/"
              element={
                user ? (
                  <>
                    <section>
                      <h2>Portfolio overview</h2>
                      <p>
                        {workspace
                          ? workspace.name
                          : "Create a workspace to begin."}
                      </p>
                      <p>
                        {brand
                          ? `Current brand: ${brand.name}`
                          : "Select or create a brand in Portfolio."}
                      </p>
                      <p>
                        Production, publishing and analytics remain planned. No
                        platform connections are fabricated.
                      </p>
                    </section>
                    <Operations />
                  </>
                ) : (
                  <LoginForm />
                )
              }
            />
            <Route path="/portfolio" element={portfolio} />
            <Route path="/settings" element={portfolio} />
            {["/discovery", "/research"].map((path) => (
              <Route
                key={path}
                path={path}
                element={
                  user ? (
                    workspace && brand ? (
                      <Discovery
                        session={user}
                        workspace={workspace.id}
                        brand={brand}
                        brands={brands.data ?? []}
                      />
                    ) : (
                      <p>Create a workspace and brand in Portfolio first.</p>
                    )
                  ) : (
                    <LoginForm />
                  )
                }
              />
            ))}
            <Route path="/operations" element={<Operations />} />
            <Route path="*" element={<h2>Page not found</h2>} />
          </Routes>
        )}
        <footer>
          Local-first · Human-controlled publishing · No paid AI dependency
        </footer>
      </main>
    </div>
  );
}
