export interface User {
  id: number;
  telegram_id: number | null;
  username: string | null;
  full_name: string;
  email: string | null;
  trial_used: boolean;
  created_at: string;
}

export interface Plan {
  id: string;
  name: string;
  duration_days: number;
  traffic_gb: number;
  price: number;
  description: string;
  is_trial: boolean;
}

export interface Provider {
  provider: string;
  label: string;
}

export interface Subscription {
  id: number;
  plan_id: string;
  status: "trial" | "active" | "expired";
  subscription_url: string;
  traffic_limit_gb: number;
  started_at: string;
  expires_at: string;
}

export interface Payment {
  id: number;
  plan_id: string;
  amount: number;
  currency: string;
  provider: string;
  status: "pending" | "succeeded" | "cancelled";
  created_at: string;
  paid_at: string | null;
}

export interface PaymentCreateResult {
  ok: boolean;
  payment_id: number | null;
  confirmation_url: string | null;
  error: string | null;
}

export interface PaymentStatusResult {
  ok: boolean;
  status: string;
  subscription_url: string | null;
  expires_at: string | null;
  error: string | null;
}
