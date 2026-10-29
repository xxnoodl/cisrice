import { useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Brand, type SessionInfo } from "./api";

type Rights = {
  id: string;
  title: string;
  source_url: string;
  adapter: string;
  basis: string;
  license: string;
  evidence: string;
  attribution: string;
  restrictions: string;
  status: string;
};
type Candidate = { id: string; title: string; original_url: string };
type Job = {
  id: string;
  state: string;
  progress: number;
  attempts: number;
  max_attempts: number;
  error_code: string;
  cancel_requested: boolean;
};
type Asset = {
  id: string;
  rights_id: string;
  title: string;
  export_name: string;
  sha256: string;
  size_bytes: number;
  duration: number;
  width: number;
  height: number;
  video_codec: string;
  audio_codec: string | null;
  rights_status: string;
};

export function MediaLibrary(props: {
  workspace: string;
  brand: Brand;
  brands: Brand[];
  session: SessionInfo;
}) {
  return <MediaContext key={props.workspace + props.brand.id} {...props} />;
}

function MediaContext({
  workspace,
  brand,
  brands,
  session,
}: {
  workspace: string;
  brand: Brand;
  brands: Brand[];
  session: SessionInfo;
}) {
  const client = useQueryClient();
  const root = `/workspaces/${workspace}/brands/${brand.id}/media`;
  const editable = brand.role !== "viewer";
  const [candidate, setCandidate] = useState("");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [offset, setOffset] = useState(0);
  const [sourceBrand, setSourceBrand] = useState("");
  const [sourceAsset, setSourceAsset] = useState("");
  const [destinationRights, setDestinationRights] = useState("");
  const keys = useRef(new Map<string, string>());
  const rights = useQuery({
    queryKey: ["media", root, "rights"],
    queryFn: () => api<Rights[]>(root + "/rights"),
  });
  const jobs = useQuery({
    queryKey: ["media", root, "jobs"],
    queryFn: () => api<Job[]>(root + "/jobs"),
    refetchInterval: 2500,
  });
  const assets = useQuery({
    queryKey: ["media", root, "assets", offset],
    queryFn: () => api<Asset[]>(root + "/assets?offset=" + offset),
    refetchInterval: 2500,
  });
  const candidates = useQuery({
    queryKey: ["media", root, "candidates"],
    queryFn: () =>
      api<Candidate[]>(
        `/workspaces/${workspace}/brands/${brand.id}/discovery/candidates?status=APPROVED&order=newest`,
      ),
  });
  const reusable = useQuery({
    queryKey: ["media", workspace, sourceBrand, "reuse-assets"],
    queryFn: () =>
      api<Asset[]>(
        `/workspaces/${workspace}/brands/${sourceBrand}/media/assets`,
      ),
    enabled: !!sourceBrand,
  });
  const action = useMutation({
    mutationFn: ({ path, data }: { path: string; data?: unknown }) =>
      api(root + path, "POST", data, session.csrf_token),
    onSuccess: async () => {
      await client.cancelQueries({ queryKey: ["media"] });
      await client.invalidateQueries({ queryKey: ["media"] });
    },
  });
  function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    action.mutate({
      path: "/rights",
      data: {
        candidate_id: candidate || null,
        title,
        source_url: url,
        adapter: data.get("adapter"),
        basis: data.get("basis"),
        license: data.get("license"),
        evidence: data.get("evidence"),
        attribution: data.get("attribution"),
        restrictions: data.get("restrictions"),
        confirmed: data.get("confirmed") === "on",
      },
    });
  }
  function request(rightsId: string) {
    if (!keys.current.has(rightsId))
      keys.current.set(rightsId, crypto.randomUUID());
    action.mutate({
      path: "/requests",
      data: {
        rights_id: rightsId,
        idempotency_key: keys.current.get(rightsId),
      },
    });
  }
  const error =
    action.error ??
    rights.error ??
    jobs.error ??
    assets.error ??
    candidates.error ??
    reusable.error;
  return (
    <>
      <section aria-labelledby="media-title">
        <h2 id="media-title">Media Library — {brand.name}</h2>
        <p>
          Review rights before acquiring media. A public URL or research
          approval does not grant reuse rights. Originals are stored immutably
          and validated locally.
        </p>
        {error && <p role="alert">{error.message}</p>}
        {action.isPending && <p role="status">Saving request…</p>}
        {action.isSuccess && (
          <p role="status">
            Saved. Check the rights records and job history below.
          </p>
        )}
        {editable && (
          <details open>
            <summary>Rights review and acquisition</summary>
            <form onSubmit={review}>
              <label>
                Approved research candidate
                <select
                  value={candidate}
                  onChange={(e) => {
                    setCandidate(e.target.value);
                    const c = candidates.data?.find(
                      (c) => c.id === e.target.value,
                    );
                    if (c) {
                      setTitle(c.title.slice(0, 200));
                      setUrl(c.original_url);
                    }
                  }}
                >
                  <option value="">Manual source / owned media</option>
                  {candidates.data?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Media title
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                  maxLength={200}
                />
              </label>
              <label>
                Authorized HTTPS source URL
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                  maxLength={2048}
                />
              </label>
              <label>
                Acquisition adapter
                <select name="adapter">
                  <option value="direct">Direct HTTPS video file</option>
                  <option value="ytdlp">
                    yt-dlp progressive HTTPS format (limited support)
                  </option>
                </select>
              </label>
              <label>
                Rights basis
                <select name="basis">
                  <option value="OWNED">I own this media</option>
                  <option value="LICENSED">License permits use</option>
                  <option value="PERMISSION">
                    Permission from rights holder
                  </option>
                </select>
              </label>
              <label>
                License or ownership description
                <input name="license" required maxLength={300} />
              </label>
              <label>
                Permission evidence / license reference
                <textarea name="evidence" required maxLength={5000} />
              </label>
              <label>
                Required attribution
                <textarea name="attribution" maxLength={3000} />
              </label>
              <label>
                Usage restrictions
                <textarea name="restrictions" maxLength={3000} />
              </label>
              <label>
                <input type="checkbox" name="confirmed" required /> I confirm
                the evidence permits this acquisition and intended use, and the
                source platform permits downloading.
              </label>
              <button disabled={action.isPending}>
                Record rights approval
              </button>
            </form>
          </details>
        )}
      </section>
      <section>
        <h2>Rights decisions</h2>
        <p>
          Latest 50 decisions. Revocation blocks new acquisition, downloads and
          reuse; retained originals and audit records are preserved.
        </p>
        {rights.data?.length === 0 && (
          <p>
            No rights decisions yet. Unknown rights cannot enter the download
            queue.
          </p>
        )}
        {rights.data?.map((r) => (
          <article key={r.id}>
            <h3>{r.title}</h3>
            <p>
              {r.status} · {r.basis} · {r.adapter}
            </p>
            <details>
              <summary>Rights evidence for {r.title}</summary>
              <p>{r.license}</p>
              <p>{r.evidence}</p>
              <p>Attribution: {r.attribution || "None recorded"}</p>
              <p>Restrictions: {r.restrictions || "None recorded"}</p>
              <p>{r.source_url}</p>
            </details>
            {editable && r.status === "APPROVED" && (
              <>
                <button
                  disabled={action.isPending}
                  onClick={() => request(r.id)}
                >
                  Acquire {r.title}
                </button>
                <button
                  disabled={action.isPending}
                  onClick={() =>
                    action.mutate({ path: `/rights/${r.id}/revoke` })
                  }
                >
                  Revoke rights for {r.title}
                </button>
              </>
            )}
          </article>
        ))}
      </section>
      <section>
        <h2>Acquisition jobs</h2>
        <p>
          PostgreSQL holds durable state. Downloads and local validation are
          serialized. Cancellation may take several seconds.
        </p>
        <div className="table-scroll">
          <table>
            <caption>Latest 50 media jobs</caption>
            <thead>
              <tr>
                <th>Job</th>
                <th>State</th>
                <th>Progress</th>
                <th>Attempts</th>
                <th>Error</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {jobs.data?.map((j) => (
                <tr key={j.id}>
                  <td>{j.id.slice(0, 8)}</td>
                  <td>
                    {j.state}
                    {j.cancel_requested ? " · cancellation requested" : ""}
                  </td>
                  <td>
                    <progress
                      max={100}
                      value={j.progress}
                      aria-label={`Progress for job ${j.id}`}
                    />{" "}
                    {j.progress}%
                  </td>
                  <td>
                    {j.attempts}/{j.max_attempts}
                  </td>
                  <td>{j.error_code || "—"}</td>
                  <td>
                    {editable &&
                      ["QUEUED", "RUNNING", "RETRY"].includes(j.state) && (
                        <button
                          disabled={action.isPending || j.cancel_requested}
                          onClick={() =>
                            action.mutate({ path: `/jobs/${j.id}/cancel` })
                          }
                        >
                          Cancel job {j.id.slice(0, 8)}
                        </button>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {jobs.data?.some((j) => j.state === "FAILED") && (
          <p>
            For a corrected or failed acquisition, create a new rights decision
            and submit a new request. Automatic retries have a bounded budget.
          </p>
        )}
      </section>
      <section>
        <h2>Canonical media</h2>
        {assets.isPending && <p role="status">Loading media…</p>}
        {assets.data?.length === 0 && (
          <p>No validated assets in this brand yet.</p>
        )}
        {assets.data?.map((a) => (
          <article key={a.id}>
            <h3>{a.title}</h3>
            <p>
              {a.width} × {a.height} · {a.duration.toFixed(2)} seconds ·{" "}
              {(a.size_bytes / 1024 ** 2).toFixed(2)} MiB · {a.video_codec} /{" "}
              {a.audio_codec ?? "No audio"}
            </p>
            <p>Rights: {a.rights_status}</p>
            <details>
              <summary>Object fingerprint and export name</summary>
              <p>{a.sha256}</p>
              <p>{a.export_name}</p>
            </details>
            {a.rights_status === "APPROVED" && (
              <>
                <video
                  className="media-preview"
                  controls
                  preload="metadata"
                  src={"/api" + root + `/assets/${a.id}/file`}
                  aria-label={"Preview " + a.title}
                />
                <p>
                  <a
                    href={"/api" + root + `/assets/${a.id}/file`}
                    download={a.export_name}
                  >
                    Download {a.title}
                  </a>
                </p>
              </>
            )}
          </article>
        ))}
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          Previous assets
        </button>
        <span> Page {offset / 50 + 1} </span>
        <button
          disabled={!assets.data || assets.data.length < 50}
          onClick={() => setOffset(offset + 50)}
        >
          Next assets
        </button>
      </section>
      {editable && (
        <section>
          <h2>Reuse an authorized asset</h2>
          <p>
            Choose a visible source brand and a separate destination rights
            decision covering the same source URL. Reuse creates a brand
            reference without copying the canonical file.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              action.mutate({
                path: "/reuse",
                data: {
                  source_brand_id: sourceBrand,
                  source_asset_id: sourceAsset,
                  destination_rights_id: destinationRights,
                },
              });
            }}
          >
            <label>
              Source brand
              <select
                required
                value={sourceBrand}
                onChange={(e) => {
                  setSourceBrand(e.target.value);
                  setSourceAsset("");
                }}
              >
                <option value="">Choose source brand</option>
                {brands
                  .filter((b) => b.role !== "viewer")
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Source media asset
              <select
                required
                value={sourceAsset}
                onChange={(e) => setSourceAsset(e.target.value)}
              >
                <option value="">Choose source asset</option>
                {reusable.data
                  ?.filter((a) => a.rights_status === "APPROVED")
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.title}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Destination rights decision
              <select
                required
                value={destinationRights}
                onChange={(e) => setDestinationRights(e.target.value)}
              >
                <option value="">Choose approved rights</option>
                {rights.data
                  ?.filter((r) => r.status === "APPROVED")
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title}
                    </option>
                  ))}
              </select>
            </label>
            <button disabled={action.isPending}>
              Link existing media to this brand
            </button>
          </form>
        </section>
      )}
    </>
  );
}
