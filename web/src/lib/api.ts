import type {
  Payment,
  PaymentCreateResult,
  PaymentStatusResult,
  Plan,
  Provider,
  Subscription,
  User,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ──────────────── Token storage ────────────────

const TOKEN_KEY = "vpnbox_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ──────────────── HTTP client ────────────────

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  requireAuth = false,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (requireAuth) {
    const token = getToken();
    if (!token) throw new ApiError(401, "Not authenticated");
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const err = await res.json();
      message = err.detail ?? message;
    } catch {}
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ──────────────── Auth ────────────────

export async function authTelegram(initData: string): Promise<string> {
  const data = await request<{ access_token: string }>("/api/auth/telegram", {
    method: "POST",
    body: JSON.stringify({ init_data: initData }),
  });
  return data.access_token;
}

export async function register(payload: {
  email: string;
  password: string;
  full_name: string;
  recaptcha_token: string;
}): Promise<string> {
  const data = await request<{ access_token: string }>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data.access_token;
}

export async function login(email: string, password: string): Promise<string> {
  const data = await request<{ access_token: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return data.access_token;
}

export async function fetchMe(): Promise<User> {
  return request<User>("/api/auth/me", {}, true);
}

// ──────────────── Plans & Providers ────────────────

export async function fetchPlans(): Promise<Plan[]> {
  return request<Plan[]>("/api/plans");
}

export async function fetchProviders(): Promise<Provider[]> {
  return request<Provider[]>("/api/providers");
}

// ──────────────── Subscription ────────────────

export async function fetchSubscription(): Promise<Subscription | null> {
  const result = await request<Subscription | null>("/api/subscription", {}, true);
  return result;
}

export async function activateTrial(): Promise<{
  ok: boolean;
  subscription_url?: string;
  expires_at?: string;
  error?: string;
}> {
  return request("/api/subscription/trial", { method: "POST" }, true);
}

// ──────────────── Payments ────────────────

export async function createPayment(
  plan_id: string,
  provider: string,
): Promise<PaymentCreateResult> {
  return request<PaymentCreateResult>(
    "/api/payment/create",
    {
      method: "POST",
      body: JSON.stringify({ plan_id, provider }),
    },
    true,
  );
}

export async function checkPaymentStatus(
  payment_id: number,
): Promise<PaymentStatusResult> {
  return request<PaymentStatusResult>(
    `/api/payment/${payment_id}/status`,
    {},
    true,
  );
}

export async function fetchPaymentHistory(): Promise<Payment[]> {
  return request<Payment[]>("/api/payment/history", {}, true);
}

export async function cancelPayment(payment_id: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/payment/${payment_id}/cancel`,
    { method: "POST" },
    true,
  );
}

export { ApiError };
