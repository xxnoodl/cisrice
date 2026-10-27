import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type Account,
  type Audit,
  type Brand,
  type Grant,
  type Niche,
  type SessionInfo,
  type StyleGuide,
  type Workspace,
} from "./api";

function values(event: FormEvent<HTMLFormElement>): Record<string, string> {
  return Object.fromEntries(
    new FormData(event.currentTarget).entries(),
  ) as Record<string, string>;
}
export function Field({
  label,
  name,
  value = "",
  required = true,
  type = "text",
}: {
  label: string;
  name: string;
  value?: string;
  required?: boolean;
  type?: string;
}) {
  return (
    <label>
      {label}
      <input
        name={name}
        defaultValue={value}
        required={required}
        type={type}
        maxLength={type === "email" ? 254 : 120}
      />
    </label>
  );
}
function ActionForm({
  label,
  path,
  method = "POST",
  csrf,
  children,
  transform,
  after,
}: {
  label: string;
  path: string;
  method?: string;
  csrf: string;
  children: ReactNode;
  transform?: (data: Record<string, string>) => unknown;
  after?: (result: unknown) => void;
}) {
  const client = useQueryClient();
  const [saved, setSaved] = useState(false);
  const action = useMutation({
    mutationFn: (data: Record<string, string>) =>
      api<unknown>(path, method, transform ? transform(data) : data, csrf),
    onSuccess: (data) => {
      setSaved(true);
      void client.invalidateQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      after?.(data);
    },
  });
  return (
    <form
      aria-label={label}
      onSubmit={(e) => {
        e.preventDefault();
        setSaved(false);
        action.mutate(values(e));
      }}
    >
      {children}
      <button disabled={action.isPending}>
        {action.isPending ? "Saving…" : label}
      </button>
      {action.error && <p role="alert">{action.error.message}</p>}
      {saved && <p role="status">Saved</p>}
    </form>
  );
}
function Revoke({
  path,
  csrf,
  onDone,
}: {
  path: string;
  csrf: string;
  onDone?: () => void;
}) {
  const client = useQueryClient();
  const action = useMutation({
    mutationFn: () => api<void>(path, "DELETE", undefined, csrf),
    onSuccess: () => {
      void client.invalidateQueries({
        predicate: (q) => q.queryKey[0] !== "session",
      });
      onDone?.();
    },
  });
  return (
    <>
      <button
        className="secondary"
        disabled={action.isPending}
        onClick={() => action.mutate()}
      >
        Revoke access
      </button>
      {action.error && <span role="alert">{action.error.message}</span>}
    </>
  );
}
function Access({
  base,
  workspaceBase,
  csrf,
  accounts,
}: {
  base: string;
  workspaceBase: string;
  csrf: string;
  accounts: Account[];
}) {
  const members = useQuery({
    queryKey: ["members", workspaceBase],
    queryFn: () => api<Grant[]>(workspaceBase + "/members"),
  });
  const grants = useQuery({
    queryKey: ["grants", base],
    queryFn: () => api<Grant[]>(base + "/permissions"),
  });
  const [account, setAccount] = useState("");
  const selected = accounts.find((row) => row.id === account) ?? accounts[0];
  const accountPath = selected ? base + "/accounts/" + selected.id : "";
  const accountGrants = useQuery({
    queryKey: ["account-grants", accountPath],
    queryFn: () => api<Grant[]>(accountPath + "/permissions"),
    enabled: !!accountPath,
  });
  return (
    <section>
      <h2>Access management</h2>
      <p>
        Workspace owners manage the entire workspace. Members need brand access
        and separate account access. Users must first be created by the local
        operator.
      </p>
      <h3>Workspace members</h3>
      <ActionForm
        label="Save workspace member"
        path={workspaceBase + "/members"}
        method="PUT"
        csrf={csrf}
      >
        <Field name="email" label="Member email" type="email" />
        <label>
          Workspace role
          <select name="role">
            <option value="member">Member</option>
            <option value="owner">Owner</option>
          </select>
        </label>
      </ActionForm>
      <ul>
        {members.data?.map((row) => (
          <li key={row.user_id}>
            {row.email} · {row.role}{" "}
            <Revoke
              path={workspaceBase + "/members/" + row.user_id}
              csrf={csrf}
            />
          </li>
        ))}
      </ul>
      <h3>Brand permissions</h3>
      <ActionForm
        label="Save brand permission"
        path={base + "/permissions"}
        method="PUT"
        csrf={csrf}
      >
        <Field name="email" label="Brand member email" type="email" />
        <label>
          Brand role
          <select name="role">
            <option value="viewer">Viewer</option>
            <option value="editor">Editor</option>
          </select>
        </label>
      </ActionForm>
      <ul>
        {grants.data?.map((row) => (
          <li key={row.user_id}>
            {row.email} · {row.role}{" "}
            <Revoke path={base + "/permissions/" + row.user_id} csrf={csrf} />
          </li>
        ))}
      </ul>
      {selected && (
        <>
          <h3>Account permissions</h3>
          <label>
            Account to manage
            <select
              value={selected.id}
              onChange={(e) => setAccount(e.target.value)}
            >
              {accounts.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.platform} · {row.handle}
                </option>
              ))}
            </select>
          </label>
          <ActionForm
            key={accountPath}
            label="Save account permission"
            path={accountPath + "/permissions"}
            method="PUT"
            csrf={csrf}
          >
            <Field name="email" label="Account member email" type="email" />
            <label>
              Account role
              <select name="role">
                <option value="viewer">Viewer</option>
                <option value="editor">Editor</option>
              </select>
            </label>
          </ActionForm>
          <ul>
            {accountGrants.data?.map((row) => (
              <li key={row.user_id}>
                {row.email} · {row.role}{" "}
                <Revoke
                  path={accountPath + "/permissions/" + row.user_id}
                  csrf={csrf}
                />
              </li>
            ))}
          </ul>
        </>
      )}
      {(members.error || grants.error || accountGrants.error) && (
        <p role="alert">Could not load permissions. Refresh to retry.</p>
      )}
    </section>
  );
}
function BrandSettings({
  brand,
  base,
  csrf,
}: {
  brand: Brand;
  base: string;
  csrf: string;
}) {
  const style = useQuery({
    queryKey: ["style", base],
    queryFn: () => api<StyleGuide>(base + "/style-guide"),
  });
  const writable = brand.role !== "viewer";
  return (
    <section>
      <h2>Brand identity and style</h2>
      <p>
        Access: {brand.role}. Publishing requires human approval; account
        registration does not connect OAuth.
      </p>
      {writable ? (
        <ActionForm
          label="Save brand identity"
          method="PATCH"
          path={base}
          csrf={csrf}
        >
          <Field label="Brand name" name="name" value={brand.name} />
          <label>
            Description
            <textarea
              name="description"
              maxLength={2000}
              defaultValue={brand.description}
            />
          </label>
        </ActionForm>
      ) : (
        <p>
          {brand.name}: {brand.description || "No description."}
        </p>
      )}
      {style.isPending && <p role="status">Loading style guide…</p>}
      {style.error && <p role="alert">{style.error.message}</p>}
      {style.data &&
        (writable ? (
          <ActionForm
            label="Save style guide"
            method="PUT"
            path={base + "/style-guide"}
            csrf={csrf}
            transform={(data) => ({
              ...data,
              colors: data.colors
                .split(",")
                .map((x) => x.trim())
                .filter(Boolean),
            })}
          >
            <label>
              Voice and editorial preferences
              <textarea
                name="voice"
                maxLength={2000}
                defaultValue={style.data.voice}
              />
            </label>
            <label>
              Audience
              <textarea
                name="audience"
                maxLength={1000}
                defaultValue={style.data.audience}
              />
            </label>
            <Field
              label="Typography"
              name="typography"
              value={style.data.typography}
              required={false}
            />
            <Field
              label="Colors (comma-separated #RRGGBB)"
              name="colors"
              value={style.data.colors.join(", ")}
              required={false}
            />
          </ActionForm>
        ) : (
          <dl>
            <dt>Voice</dt>
            <dd>{style.data.voice || "Not configured"}</dd>
            <dt>Audience</dt>
            <dd>{style.data.audience || "Not configured"}</dd>
            <dt>Typography</dt>
            <dd>{style.data.typography || "Not configured"}</dd>
            <dt>Colors</dt>
            <dd>{style.data.colors.join(", ") || "Not configured"}</dd>
          </dl>
        ))}
    </section>
  );
}

export function Portfolio({
  session,
  workspaces,
  workspace,
  niches,
  brands,
  brand,
  select,
}: {
  session: SessionInfo;
  workspaces: Workspace[];
  workspace?: Workspace;
  niches: Niche[];
  brands: Brand[];
  brand?: Brand;
  select: (workspace: string, niche?: string, brand?: string) => void;
}) {
  const csrf = session.csrf_token;
  const root = workspace ? "/workspaces/" + workspace.id : "";
  const base = brand ? root + "/brands/" + brand.id : "";
  const accounts = useQuery({
    queryKey: ["accounts", base],
    queryFn: () => api<Account[]>(base + "/accounts"),
    enabled: !!base,
  });
  const auditPath =
    workspace?.role === "owner"
      ? root + "/audit"
      : brand
        ? base + "/audit"
        : "";
  const audit = useQuery({
    queryKey: ["audit", auditPath],
    queryFn: () => api<Audit[]>(auditPath),
    enabled: !!auditPath,
  });
  const [editingAccount, setEditingAccount] = useState<string | null>(null);
  const editable = accounts.data?.find((row) => row.id === editingAccount);
  return (
    <>
      <section>
        <h2>Portfolio hierarchy</h2>
        <p>
          {workspaces.length} accessible workspace
          {workspaces.length === 1 ? "" : "s"}. Select a workspace and brand
          above to change context.
        </p>
        <ActionForm
          label="Create workspace"
          path="/workspaces"
          csrf={csrf}
          after={(result) => select((result as Workspace).id)}
        >
          <Field label="Workspace name" name="name" />
        </ActionForm>
        {workspace && (
          <>
            <h3>{workspace.name}</h3>
            <ul>
              {niches.map((niche) => (
                <li key={niche.id}>
                  <strong>{niche.name}</strong>
                  <ul>
                    {brands
                      .filter((row) => row.niche_id === niche.id)
                      .map((row) => (
                        <li key={row.id}>
                          <button
                            className="link-button"
                            aria-current={
                              row.id === brand?.id ? "true" : undefined
                            }
                            onClick={() =>
                              select(workspace.id, niche.id, row.id)
                            }
                          >
                            {row.name}
                          </button>{" "}
                          · {row.role}
                        </li>
                      ))}
                  </ul>
                </li>
              ))}
            </ul>
          </>
        )}
        {workspace?.role === "owner" && (
          <div className="form-grid">
            <div>
              <h3>Add niche</h3>
              <ActionForm
                label="Create niche"
                path={root + "/niches"}
                csrf={csrf}
              >
                <Field label="Niche name" name="name" />
              </ActionForm>
            </div>
            {!!niches.length && (
              <div>
                <h3>Add brand</h3>
                <ActionForm
                  label="Create brand"
                  path={root + "/brands"}
                  csrf={csrf}
                  after={(result) => {
                    const row = result as Brand;
                    select(row.workspace_id, row.niche_id, row.id);
                  }}
                >
                  <Field label="New brand name" name="name" />
                  <label>
                    Niche
                    <select name="niche_id">
                      {niches.map((row) => (
                        <option key={row.id} value={row.id}>
                          {row.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </ActionForm>
              </div>
            )}
          </div>
        )}
      </section>
      {brand && (
        <>
          <BrandSettings key={brand.id} brand={brand} base={base} csrf={csrf} />
          <section>
            <h2>Platform accounts</h2>
            <p>
              Registered accounts are not OAuth-connected. Publishing and
              provider authentication arrive in a later milestone.
            </p>
            {accounts.error && <p role="alert">{accounts.error.message}</p>}
            <div className="table-scroll">
              <table>
                <caption>Accounts for {brand.name}</caption>
                <thead>
                  <tr>
                    <th scope="col">Platform</th>
                    <th scope="col">Handle</th>
                    <th scope="col">Connection</th>
                    <th scope="col">Time zone</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.data?.map((row) => (
                    <tr key={row.id}>
                      <td>{row.platform}</td>
                      <td>{row.handle}</td>
                      <td>
                        <span className="badge">
                          {row.connection_status.replaceAll("_", " ")}
                        </span>
                      </td>
                      <td>{row.timezone}</td>
                      <td>
                        {row.can_edit && (
                          <button
                            className="secondary"
                            onClick={() => setEditingAccount(row.id)}
                          >
                            Edit {row.handle}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!accounts.data?.length && !accounts.isPending && (
              <p>No platform accounts visible in this brand.</p>
            )}
            {brand.role !== "viewer" && (
              <>
                <h3>
                  {editable ? "Edit registered account" : "Register an account"}
                </h3>
                <ActionForm
                  key={editable?.id ?? base}
                  label={editable ? "Save account" : "Register account"}
                  path={
                    editable
                      ? base + "/accounts/" + editable.id
                      : base + "/accounts"
                  }
                  method={editable ? "PATCH" : "POST"}
                  csrf={csrf}
                  after={() => setEditingAccount(null)}
                >
                  <label>
                    Platform
                    <select
                      name="platform"
                      defaultValue={editable?.platform ?? "youtube"}
                    >
                      {["youtube", "instagram", "facebook", "tiktok", "x"].map(
                        (platform) => (
                          <option key={platform}>{platform}</option>
                        ),
                      )}
                    </select>
                  </label>
                  <Field
                    name="handle"
                    label="Account handle"
                    value={editable?.handle}
                  />
                  <Field
                    name="display_name"
                    label="Display name"
                    value={editable?.display_name}
                    required={false}
                  />
                  <label>
                    Profile URL
                    <input
                      name="profile_url"
                      type="url"
                      maxLength={2048}
                      defaultValue={editable?.profile_url ?? ""}
                    />
                  </label>
                  <Field
                    name="timezone"
                    label="Account time zone"
                    value={editable?.timezone ?? "UTC"}
                  />
                </ActionForm>
                {editable && (
                  <button
                    className="secondary"
                    onClick={() => setEditingAccount(null)}
                  >
                    Cancel account edit
                  </button>
                )}
              </>
            )}
          </section>
          {workspace?.role === "owner" && (
            <Access
              key={base}
              base={base}
              workspaceBase={root}
              csrf={csrf}
              accounts={accounts.data ?? []}
            />
          )}
        </>
      )}
      {auditPath && (
        <section>
          <h2>Audit history</h2>
          <p>
            {workspace?.role === "owner" ? "Workspace" : "Selected brand"}{" "}
            changes, newest first.
          </p>
          {audit.error && <p role="alert">{audit.error.message}</p>}
          <div className="table-scroll">
            <table>
              <caption>Recent authorized changes</caption>
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">Event</th>
                  <th scope="col">Actor</th>
                </tr>
              </thead>
              <tbody>
                {audit.data?.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <time dateTime={row.created_at}>
                        {new Date(row.created_at).toLocaleString()}
                      </time>
                    </td>
                    <td>{row.event_type}</td>
                    <td>
                      {row.actor_id === session.user.id
                        ? "You"
                        : (row.actor_id ?? "Local operator")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
