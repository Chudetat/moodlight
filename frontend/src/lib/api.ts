import { API_BASE_URL } from "./constants";
import type { ApiError } from "./types";

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;

    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!res.ok) {
      const body = (await res.json().catch(() => ({
        detail: res.statusText,
      }))) as ApiError;
      throw new ApiClientError(res.status, body.detail || res.statusText);
    }

    // Handle PDF responses
    const contentType = res.headers.get("content-type");
    if (contentType?.includes("application/pdf")) {
      return (await res.blob()) as unknown as T;
    }

    return (await res.json()) as T;
  }

  async get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
    const searchParams = new URLSearchParams();
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
          searchParams.set(key, String(value));
        }
      }
    }
    const query = searchParams.toString();
    const fullPath = query ? `${path}?${query}` : path;
    return this.request<T>(fullPath);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }
}

export class ApiClientError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
  }
}

// Client for browser-side calls through Next.js API proxy
export const api = new ApiClient("/api/proxy");

// Direct client for server-side calls (SSR / API routes)
export const directApi = new ApiClient(API_BASE_URL);
