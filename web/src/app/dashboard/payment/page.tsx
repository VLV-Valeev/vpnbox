"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  ExternalLink,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  CreditCard,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  fetchPlans,
  fetchProviders,
  createPayment,
  checkPaymentStatus,
  cancelPayment,
} from "@/lib/api";
import type { Plan, Provider } from "@/types";

const POLL_INTERVAL_MS = 4000;
const POLL_TIMEOUT_MS = 15 * 60 * 1000;

// ──────────────── Provider icons ────────────────

type ProviderMeta = {
  abbr: string;
  bg: string;
  text: string;
  border: string;
};

const PROVIDER_META: Record<string, ProviderMeta> = {
  yookassa: {
    abbr: "ЮK",
    bg: "bg-amber-50",
    text: "text-amber-700",
    border: "border-amber-200",
  },
  freekassa: {
    abbr: "FK",
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    border: "border-emerald-200",
  },
  platega: {
    abbr: "PT",
    bg: "bg-blue-50",
    text: "text-blue-700",
    border: "border-blue-200",
  },
  cryptocloud: {
    abbr: "₿",
    bg: "bg-orange-50",
    text: "text-orange-700",
    border: "border-orange-200",
  },
  stars: {
    abbr: "★",
    bg: "bg-sky-50",
    text: "text-sky-700",
    border: "border-sky-200",
  },
};

function ProviderIcon({ name }: { name: string }) {
  const meta = PROVIDER_META[name] ?? {
    abbr: name.slice(0, 2).toUpperCase(),
    bg: "bg-muted",
    text: "text-muted-foreground",
    border: "border-border",
  };
  return (
    <div
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border text-sm font-bold ${meta.bg} ${meta.text} ${meta.border}`}
    >
      {meta.abbr}
    </div>
  );
}

// ──────────────── Plan card ────────────────

function PlanCard({
  plan,
  selected,
  onSelect,
}: {
  plan: Plan;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full rounded-xl border p-4 text-left transition-all ${
        selected
          ? "border-indigo-400 bg-indigo-50 ring-1 ring-indigo-400"
          : "hover:border-muted-foreground/30 hover:bg-muted/20"
      }`}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
              selected ? "border-indigo-600 bg-indigo-600" : "border-muted-foreground/30"
            }`}
          >
            {selected && <div className="h-1.5 w-1.5 rounded-full bg-white" />}
          </div>
          <div>
            <p className="font-semibold">{plan.name}</p>
            <p className="text-sm text-muted-foreground">{plan.description}</p>
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xl font-bold">{plan.price} ₽</p>
          <p className="text-xs text-muted-foreground">{plan.duration_days} дней</p>
        </div>
      </div>
    </button>
  );
}

// ──────────────── Provider button ────────────────

function ProviderButton({
  provider,
  selected,
  onSelect,
}: {
  provider: Provider;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`flex items-center gap-2.5 rounded-xl border px-4 py-3 text-sm font-medium transition-all ${
        selected
          ? "border-indigo-400 bg-indigo-50 ring-1 ring-indigo-400 text-indigo-700"
          : "hover:border-muted-foreground/30 hover:bg-muted/20 text-foreground"
      }`}
    >
      <ProviderIcon name={provider.provider} />
      <span>{provider.label}</span>
    </button>
  );
}

type PollingState = "idle" | "polling" | "succeeded" | "cancelled" | "timeout";

// ──────────────── Main component ────────────────

function PaymentContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const preselectedPlan = searchParams.get("plan");

  const [plans, setPlans] = useState<Plan[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<string>(preselectedPlan ?? "");
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [paymentId, setPaymentId] = useState<number | null>(null);
  const [confirmationUrl, setConfirmationUrl] = useState<string | null>(null);
  const [pollingState, setPollingState] = useState<PollingState>("idle");

  useEffect(() => {
    Promise.all([fetchPlans(), fetchProviders()])
      .then(([p, pr]) => {
        setPlans(p);
        const filtered = pr.filter((x) => x.provider !== "stars");
        setProviders(filtered);
        if (!selectedPlan && p.length > 0) setSelectedPlan(p[0].id);
        if (filtered.length > 0) setSelectedProvider(filtered[0].provider);
      })
      .catch(() => setError("Не удалось загрузить тарифы."))
      .finally(() => setLoading(false));
  }, []);

  // Polling
  useEffect(() => {
    if (!paymentId || pollingState !== "polling") return;
    let stopped = false;
    const startedAt = Date.now();

    const poll = async () => {
      while (!stopped) {
        if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
          if (!stopped) setPollingState("timeout");
          return;
        }
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        if (stopped) return;
        try {
          const result = await checkPaymentStatus(paymentId);
          if (result.status === "succeeded") { setPollingState("succeeded"); return; }
          if (result.status === "cancelled") { setPollingState("cancelled"); return; }
        } catch {
          // keep polling on network errors
        }
      }
    };

    poll();
    return () => { stopped = true; };
  }, [paymentId, pollingState]);

  const handleCreatePayment = async () => {
    if (!selectedPlan || !selectedProvider) return;
    setError(null);
    setCreating(true);
    try {
      const result = await createPayment(selectedPlan, selectedProvider);
      if (!result.ok || !result.payment_id || !result.confirmation_url) {
        setError(result.error ?? "Не удалось создать платёж. Попробуйте позже.");
        return;
      }
      setPaymentId(result.payment_id);
      setConfirmationUrl(result.confirmation_url);
      setPollingState("polling");
    } catch {
      setError("Ошибка при создании платежа. Проверьте соединение и попробуйте снова.");
    } finally {
      setCreating(false);
    }
  };

  const handleCancel = async () => {
    if (!paymentId) { resetFlow(); return; }
    setCancelling(true);
    try {
      await cancelPayment(paymentId);
    } catch {
      // ignore — just reset UI
    } finally {
      setCancelling(false);
      resetFlow();
    }
  };

  const resetFlow = () => {
    setPollingState("idle");
    setPaymentId(null);
    setConfirmationUrl(null);
  };

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  // ── Success ──
  if (pollingState === "succeeded") {
    return (
      <div className="mx-auto max-w-md space-y-6">
        <Card className="border-emerald-200 bg-gradient-to-b from-emerald-50 to-white shadow-sm">
          <CardContent className="flex flex-col items-center gap-5 py-12 text-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-100">
              <CheckCircle2 className="h-10 w-10 text-emerald-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-emerald-700">Оплата прошла успешно!</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                VPN-подписка активирована. Перейдите в кабинет для получения конфигурации.
              </p>
            </div>
            <Button
              asChild
              className="bg-gradient-to-r from-indigo-600 to-violet-600 hover:opacity-90"
            >
              <Link href="/dashboard">Открыть личный кабинет</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Cancelled ──
  if (pollingState === "cancelled") {
    return (
      <div className="mx-auto max-w-md">
        <Card className="border-destructive/20">
          <CardContent className="flex flex-col items-center gap-5 py-12 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
              <XCircle className="h-8 w-8 text-destructive" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Платёж отменён</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Вы можете попробовать снова с другим тарифом или способом оплаты.
              </p>
            </div>
            <Button variant="outline" onClick={resetFlow}>
              Попробовать снова
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Waiting / polling ──
  if ((pollingState === "polling" || pollingState === "timeout") && confirmationUrl) {
    return (
      <div className="mx-auto max-w-md space-y-4">
        <Card>
          <CardHeader className="text-center pb-2">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100">
              <Clock className="h-8 w-8 text-indigo-600" />
            </div>
            <CardTitle>Ожидание оплаты</CardTitle>
            <CardDescription>
              Перейдите по ссылке и завершите оплату. Статус обновится автоматически.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Проверяем статус каждые {POLL_INTERVAL_MS / 1000} сек...
            </div>

            <Button
              asChild
              size="lg"
              className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 hover:opacity-90"
            >
              <a href={confirmationUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                Перейти к оплате
              </a>
            </Button>

            <Button
              variant="outline"
              size="lg"
              className="w-full gap-2 text-muted-foreground hover:text-destructive hover:border-destructive/50"
              onClick={handleCancel}
              disabled={cancelling}
            >
              {cancelling ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Отмена...</>
              ) : (
                <><X className="h-4 w-4" /> Отменить платёж</>
              )}
            </Button>

            {pollingState === "timeout" && (
              <Alert variant="destructive">
                <AlertDescription>
                  Время ожидания истекло. Если вы оплатили — обновите страницу через несколько минут.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Selection ──
  const selectedPlanData = plans.find((p) => p.id === selectedPlan);
  const selectedProviderData = providers.find((p) => p.provider === selectedProvider);

  return (
    <div className="mx-auto max-w-xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/dashboard" className="gap-1.5">
            <ArrowLeft className="h-4 w-4" /> Назад
          </Link>
        </Button>
        <Separator orientation="vertical" className="h-5" />
        <div>
          <h1 className="text-xl font-bold tracking-tight">Оформление подписки</h1>
          <p className="text-sm text-muted-foreground">Выберите тариф и способ оплаты</p>
        </div>
      </div>

      {/* Plans */}
      <div className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Тариф
        </h2>
        <div className="space-y-2">
          {plans.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              selected={selectedPlan === plan.id}
              onSelect={() => setSelectedPlan(plan.id)}
            />
          ))}
        </div>
      </div>

      <Separator />

      {/* Providers */}
      <div className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Способ оплаты
        </h2>
        {providers.length === 0 ? (
          <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
            Нет доступных способов оплаты. Обратитесь к администратору.
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {providers.map((p) => (
              <ProviderButton
                key={p.provider}
                provider={p}
                selected={selectedProvider === p.provider}
                onSelect={() => setSelectedProvider(p.provider)}
              />
            ))}
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Summary */}
      {selectedPlanData && selectedProviderData && (
        <Card className="border-indigo-200 bg-gradient-to-r from-indigo-50 to-violet-50">
          <CardContent className="flex items-center justify-between py-4">
            <div className="flex items-center gap-3">
              <ProviderIcon name={selectedProviderData.provider} />
              <div>
                <p className="font-semibold">{selectedPlanData.name}</p>
                <p className="text-sm text-muted-foreground">{selectedProviderData.label}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-indigo-700">{selectedPlanData.price}</p>
              <p className="text-sm text-muted-foreground">рублей</p>
            </div>
          </CardContent>
        </Card>
      )}

      <Button
        size="lg"
        className="w-full gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 shadow-md shadow-indigo-100 hover:opacity-90 hover:shadow-indigo-200"
        disabled={!selectedPlan || !selectedProvider || creating}
        onClick={handleCreatePayment}
      >
        {creating ? (
          <><Loader2 className="h-4 w-4 animate-spin" /> Создание платежа...</>
        ) : (
          <><CreditCard className="h-4 w-4" /> Перейти к оплате</>
        )}
      </Button>

      <p className="text-center text-xs text-muted-foreground">
        Нажимая кнопку, вы соглашаетесь с условиями использования сервиса
      </p>
    </div>
  );
}

export default function PaymentPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
        </div>
      }
    >
      <PaymentContent />
    </Suspense>
  );
}
