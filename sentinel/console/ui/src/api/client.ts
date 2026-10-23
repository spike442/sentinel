export type DomainClient = {
  getJson<T>(path: string, signal?: AbortSignal): Promise<T>;
  send(path: string, method: "POST" | "DELETE", failure: string, body?: unknown): Promise<void>;
};

async function failureDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === "string" ? `: ${payload.detail}` : "";
  } catch {
    return "";
  }
}

export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export function domainClient(base: string): DomainClient {
  const root = base.replace(/\/$/, "");
  return {
    getJson: (path, signal) => getJson(`${root}${path}`, signal),
    async send(path, method, failure, body) {
      const headers = body === undefined ? undefined : { "Content-Type": "application/json" };
      const payload = body === undefined ? undefined : JSON.stringify(body);
      const response = await fetch(`${root}${path}`, { method, headers, body: payload });
      if (!response.ok) {
        const detail = await failureDetail(response);
        throw new Error(`${failure} (${response.status})${detail}`);
      }
    },
  };
}
