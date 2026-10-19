export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export async function sendRequest(
  url: string,
  method: "POST" | "DELETE",
  failure: string,
  body?: unknown,
): Promise<void> {
  const headers = body === undefined ? undefined : { "Content-Type": "application/json" };
  const payload = body === undefined ? undefined : JSON.stringify(body);
  const response = await fetch(url, { method, headers, body: payload });
  if (!response.ok) throw new Error(`${failure} (${response.status})`);
}
