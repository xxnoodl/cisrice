import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Brand, type SessionInfo } from "./api";

const weights = {
  relevance: 25,
  engagement_velocity: 20,
  shares: 15,
  saves: 10,
  freshness: 10,
  novelty: 10,
  source_quality: 10,
};

type Source = {
  id: string;
  name: string;
  kind: string;
  url: string;
  enabled: boolean;
  policy_note: string;
  keywords: string[];
  quality: number;
};
type Run = {
  id: string;
  source_id: string;
  state: string;
  error: string;
  found: number;
  added: number;
  duplicates: number;
  created_at: string;
};
type Candidate = {
  id: string;
  title: string;
  original_url: string;
  summary: string;
  topics: string[];
  status: string;
  notes: string;
  score: number | null;
  components: Record<string, number | null>;
  rights_status: string;
  duplicate_title: boolean;
  observations: {
    source_id: string;
    identifier: string;
    original_url: string;
    observed_at: string;
  }[];
};

export function Discovery({
  session,
  workspace,
  brand,
  brands,
}: {
  session: SessionInfo;
  workspace: string;
  brand: Brand;
  brands: Brand[];
}) {
  return (
    <DiscoveryContext
      key={workspace + brand.id}
      session={session}
      workspace={workspace}
      brand={brand}
      brands={brands}
    />
  );
}

function DiscoveryContext({
  session,
  workspace,
  brand,
  brands,
}: {
  session: SessionInfo;
  workspace: string;
  brand: Brand;
  brands: Brand[];
}) {
  const client = useQueryClient();
  const root = `/workspaces/${workspace}/brands/${brand.id}/discovery`;
  const [status, setStatus] = useState("INBOX");
  const [search, setSearch] = useState("");
  const [topic, setTopic] = useState("");
  const [order, setOrder] = useState("score");
  const [offset, setOffset] = useState(0);
  const [kind, setKind] = useState("rss");
  const editable = brand.role !== "viewer";
  const sources = useQuery({
    queryKey: ["discovery", root, "sources"],
    queryFn: () => api<Source[]>(root + "/sources"),
  });
  const runs = useQuery({
    queryKey: ["discovery", root, "runs"],
    queryFn: () => api<Run[]>(root + "/runs"),
  });
  const query = new URLSearchParams({
    ...(status ? { status } : {}),
    search,
    topic,
    order,
    offset: String(offset),
  });
  const candidates = useQuery({
    queryKey: ["discovery", root, query.toString()],
    queryFn: () => api<Candidate[]>(root + "/candidates?" + query),
  });
  const action = useMutation({
    mutationFn: ({
      path,
      data,
      method = "POST",
    }: {
      path: string;
      data?: unknown;
      method?: string;
    }) => api(root + path, method, data, session.csrf_token),
    onSuccess: async () => {
      await client.cancelQueries({ queryKey: ["discovery"] });
      await client.invalidateQueries({ queryKey: ["discovery"] });
    },
  });
  function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    action.mutate({
      path: "/sources",
      data: {
        name: data.get("name"),
        kind,
        address: data.get("address"),
        keywords: String(data.get("keywords"))
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        quality: Number(data.get("quality")),
        policy_note: data.get("policy"),
        policy_confirmed: data.get("confirmed") === "on",
        weights: Object.fromEntries(
          Object.keys(weights).map((key) => [
            key,
            Number(data.get("weight_" + key)),
          ]),
        ),
      },
    });
  }
  const error = action.error ?? sources.error ?? runs.error ?? candidates.error;
  return (
    <>
      <section aria-labelledby="discovery-title">
        <h2 id="discovery-title">Discovery — {brand.name}</h2>
        <p>
          Manually discover metadata from permitted RSS/Atom and YouTube channel
          feeds. Research approval does not grant reuse rights. No media is
          downloaded.
        </p>
        {error && <p role="alert">{error.message}</p>}
        {action.isPending && (
          <p role="status">
            Processing request… Feed requests can take several seconds.
          </p>
        )}
        {action.isSuccess && (
          <p role="status">
            Request completed. Check the updated results and run history.
          </p>
        )}
        <h3>Source registry</h3>
        {editable && (
          <form onSubmit={add}>
            <label>
              Source name
              <input name="name" required maxLength={120} />
            </label>
            <label>
              Source type
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="rss">RSS / Atom</option>
                <option value="youtube">YouTube channel</option>
              </select>
            </label>
            <label>
              {kind === "youtube"
                ? "YouTube channel ID (UC…)"
                : "HTTPS feed URL"}
              <input name="address" required maxLength={2048} />
            </label>
            <label>
              Relevance keywords (comma separated)
              <input name="keywords" maxLength={1000} />
            </label>
            <label>
              Source quality (your assessment, 0–1)
              <input
                name="quality"
                type="number"
                min="0"
                max="1"
                step="0.05"
                defaultValue="0.5"
                required
              />
            </label>
            <label>
              Feed policy / permission evidence
              <textarea name="policy" required maxLength={1000} />
            </label>
            <label>
              <input name="confirmed" type="checkbox" required /> I have checked
              that this feed may be used for this research.
            </label>
            <details>
              <summary>Scoring weights</summary>
              <p>
                Weights are normalized over available signals. Initial scores
                are stored when a candidate is first discovered.
              </p>
              {Object.entries(weights).map(([key, value]) => (
                <label key={key}>
                  {key} weight
                  <input
                    name={"weight_" + key}
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    defaultValue={value}
                    required
                  />
                </label>
              ))}
            </details>
            <button disabled={action.isPending}>Add source</button>
          </form>
        )}
        {sources.isPending && <p role="status">Loading sources…</p>}
        <div className="table-scroll">
          <table>
            <caption>Brand sources (up to 200)</caption>
            <thead>
              <tr>
                <th>Name</th>
                <th>Feed</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.data?.map((s) => (
                <tr key={s.id}>
                  <td>
                    {s.name}
                    <details>
                      <summary>Policy and scoring inputs</summary>
                      <p>{s.policy_note}</p>
                      <p>
                        Keywords: {s.keywords.join(", ") || "Unavailable"}.
                        Quality: {s.quality}
                      </p>
                    </details>
                  </td>
                  <td>
                    <a href={s.url} target="_blank" rel="noreferrer">
                      {s.kind} feed
                    </a>
                  </td>
                  <td>{s.enabled ? "Active" : "Paused"}</td>
                  <td>
                    {editable && (
                      <>
                        <button
                          disabled={action.isPending || !s.enabled}
                          onClick={() =>
                            action.mutate({ path: `/sources/${s.id}/runs` })
                          }
                        >
                          Discover from {s.name}
                        </button>
                        <button
                          disabled={action.isPending}
                          onClick={() =>
                            action.mutate({ path: `/sources/${s.id}/toggle` })
                          }
                        >
                          {s.enabled ? "Pause" : "Resume"} {s.name}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sources.data?.length === 0 && (
          <p>
            No sources yet. Add a publisher's final HTTPS feed URL or a YouTube
            channel ID.
          </p>
        )}
      </section>
      <section aria-labelledby="inbox-title">
        <h2 id="inbox-title">Candidate inbox</h2>
        <p>
          Scores are deterministic editorial heuristics, not measured
          performance or forecasts. Missing engagement signals stay unavailable.
          Default weights: relevance 25, engagement velocity 20, shares 15,
          saves 10, freshness 10, novelty 10, source quality 10; normalized over
          available signals.
        </p>
        <div className="context">
          <label>
            Review status
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All</option>
              {["INBOX", "APPROVED", "REJECTED"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Search titles
            <input
              value={search}
              maxLength={120}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
          </label>
          <label>
            Topic filter
            <input
              value={topic}
              maxLength={100}
              onChange={(e) => {
                setTopic(e.target.value);
                setOffset(0);
              }}
            />
          </label>
          <label>
            Sort candidates
            <select
              value={order}
              onChange={(e) => {
                setOrder(e.target.value);
                setOffset(0);
              }}
            >
              <option value="score">Score</option>
              <option value="newest">Newest discovered</option>
            </select>
          </label>
        </div>
        {candidates.isPending && <p role="status">Loading candidates…</p>}
        {candidates.data?.length === 0 && (
          <p>No candidates match these filters.</p>
        )}
        {candidates.data?.map((c) => (
          <CandidateCard
            key={c.id + c.status + c.notes}
            candidate={c}
            editable={editable}
            brands={brands.filter(
              (b) => b.id !== brand.id && b.role !== "viewer",
            )}
            busy={action.isPending}
            save={(data) =>
              action.mutate({
                path: `/candidates/${c.id}`,
                method: "PATCH",
                data,
              })
            }
            route={(target) =>
              action.mutate({
                path: `/candidates/${c.id}/route`,
                data: { target_brand_id: target },
              })
            }
          />
        ))}
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          Previous candidates
        </button>
        <span> Page {offset / 50 + 1} </span>
        <button
          disabled={!candidates.data || candidates.data.length < 50}
          onClick={() => setOffset(offset + 50)}
        >
          Next candidates
        </button>
      </section>
      <section>
        <h2>Discovery history</h2>
        <p>
          Latest 50 runs. Repeated requests to the same source require a
          60-second cooldown.
        </p>
        <table>
          <caption>Recent discovery runs</caption>
          <thead>
            <tr>
              <th>Time</th>
              <th>Source</th>
              <th>Result</th>
              <th>New / duplicates</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {runs.data?.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td>
                  {sources.data?.find((s) => s.id === r.source_id)?.name ??
                    r.source_id}
                </td>
                <td>{r.state}</td>
                <td>
                  {r.added} / {r.duplicates} ({r.found} found)
                </td>
                <td>{r.error || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

function CandidateCard({
  candidate: c,
  editable,
  brands,
  busy,
  save,
  route,
}: {
  candidate: Candidate;
  editable: boolean;
  brands: Brand[];
  busy: boolean;
  save: (value: { status: string; notes: string }) => void;
  route: (target: string) => void;
}) {
  const [notes, setNotes] = useState(c.notes);
  const [target, setTarget] = useState("");
  return (
    <article className="candidate">
      <h3>
        <a href={c.original_url} target="_blank" rel="noreferrer">
          {c.title}
        </a>
      </h3>
      <p>{c.summary}</p>
      <p>
        {c.status} · Rights: {c.rights_status} · Editorial score:{" "}
        {c.score === null ? "Unavailable" : c.score + "/100"}
        {c.duplicate_title ? " · Possible duplicate title" : ""}
      </p>
      <p>Topics: {c.topics.join(", ") || "Unavailable"}</p>
      <details>
        <summary>Score components and provenance</summary>
        <dl>
          {Object.entries(c.components).map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v === null ? "Unavailable" : v.toFixed(3)}</dd>
            </div>
          ))}
        </dl>
        <ul>
          {c.observations.map((o, i) => (
            <li key={i}>
              Source {o.source_id} · {o.identifier} ·{" "}
              {new Date(o.observed_at).toLocaleString()}
            </li>
          ))}
        </ul>
      </details>
      <label>
        Research notes for {c.title}
        <textarea
          maxLength={5000}
          value={notes}
          readOnly={!editable}
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>
      {editable && (
        <>
          <button
            disabled={busy}
            onClick={() => save({ status: c.status, notes })}
          >
            Save notes
          </button>
          <button
            disabled={busy}
            onClick={() => save({ status: "APPROVED", notes })}
          >
            Approve research candidate
          </button>
          <button
            disabled={busy}
            onClick={() => save({ status: "REJECTED", notes })}
          >
            Reject candidate
          </button>
          <button
            disabled={busy}
            onClick={() => save({ status: "INBOX", notes })}
          >
            Return to inbox
          </button>
          {brands.length > 0 && (
            <>
              <label>
                Route {c.title} to brand
                <select
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                >
                  <option value="">Choose brand</option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
              <button disabled={busy || !target} onClick={() => route(target)}>
                Copy candidate to brand
              </button>
              <p>
                Copies source provenance with the source paused; private notes
                and approval stay in this brand.
              </p>
            </>
          )}
        </>
      )}
    </article>
  );
}
