/** Registered by the auth store; called when an API request gets a 401. */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function errorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const data = await response.json().catch(() => null);
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.message === "string") return data.message;
  }
  const text = await response.text().catch(() => "");
  return text || `Request failed (${response.status})`;
}

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers ?? {});
  const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
  if (!response.ok) {
    const message = await errorMessage(response);
    if (response.status === 401) {
      onUnauthorized?.();
    }
    throw new ApiError(message, response.status);
  }
  return response;
}

export async function apiJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await apiFetch(url, options);
  return response.json() as Promise<T>;
}

export function postJson<T>(url: string, body: unknown, options: RequestInit = {}): Promise<T> {
  return apiJson<T>(url, {
    ...options,
    method: "POST",
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    body: JSON.stringify(body),
  });
}

export function putJson<T>(url: string, body: unknown): Promise<T> {
  return apiJson<T>(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function del<T>(url: string): Promise<T> {
  return apiJson<T>(url, { method: "DELETE" });
}
