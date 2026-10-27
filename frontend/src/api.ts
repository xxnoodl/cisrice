export type SessionInfo = {
  user: { id: string; email: string };
  csrf_token: string;
  expires_at: string;
};
export type Workspace = { id: string; name: string; role: "owner" | "member" };
export type Niche = { id: string; workspace_id: string; name: string };
export type Brand = {
  id: string;
  workspace_id: string;
  niche_id: string;
  name: string;
  description: string;
  role: "owner" | "editor" | "viewer";
};
export type Account = {
  id: string;
  workspace_id: string;
  brand_id: string;
  platform: string;
  handle: string;
  display_name: string;
  profile_url: string;
  timezone: string;
  connection_status: string;
  can_edit: boolean;
};
export type StyleGuide = {
  voice: string;
  audience: string;
  typography: string;
  colors: string[];
};
export type Grant = { user_id: string; email: string; role: string };
export type Audit = {
  id: string;
  event_type: string;
  actor_id: string | null;
  created_at: string;
  details: Record<string, string>;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
  csrf?: string,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: {
      ...(data === undefined ? {} : { "Content-Type": "application/json" }),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail =
      typeof error.detail === "string"
        ? error.detail
        : Array.isArray(error.detail)
          ? error.detail
              .map(
                (item: { loc?: (string | number)[]; msg?: string }) =>
                  `${item.loc?.slice(1).join(".") ?? "Input"}: ${item.msg ?? "Invalid value"}`,
              )
              .join("; ")
          : "Request failed. Please retry.";
    throw new ApiError(response.status, detail);
  }
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}

export async function session(): Promise<SessionInfo | null> {
  try {
    return await api<SessionInfo>("/auth/session");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
