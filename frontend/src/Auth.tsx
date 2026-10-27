import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type SessionInfo } from "./api";

export function LoginForm() {
  const client = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const setup = useQuery({
    queryKey: ["setup"],
    queryFn: () => api<{ setup_required: boolean }>("/auth/status"),
    retry: false,
  });
  const login = useMutation({
    mutationFn: () =>
      api<SessionInfo>("/auth/login", "POST", { email, password }),
    onSuccess: (value) => {
      setPassword("");
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(["session"], value);
    },
    onError: () => setPassword(""),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate();
  }
  return (
    <section aria-labelledby="sign-in-title">
      <h2 id="sign-in-title">Sign in to Cisrice</h2>
      {setup.data?.setup_required && (
        <div className="notice">
          <p>No users have been created yet.</p>
          <details>
            <summary>Local account setup</summary>
            <p>On the Linux machine, run this from the Cisrice directory:</p>
            <pre>
              <code>
                docker compose exec api python -m app.modules.identity.cli
                create-user --email you@example.com
              </code>
            </pre>
            <p>The command prompts for a password. Then sign in here.</p>
          </details>
        </div>
      )}
      <form onSubmit={submit}>
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            required
            maxLength={254}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            minLength={12}
            maxLength={1024}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {login.error && <p role="alert">{login.error.message}</p>}
        <button disabled={login.isPending}>
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p>
        Your session stays on this device. No social platform accounts are
        connected by signing in.
      </p>
    </section>
  );
}
