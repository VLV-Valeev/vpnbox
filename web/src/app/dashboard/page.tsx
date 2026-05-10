"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Wifi,
  WifiOff,
  Calendar,
  Clock,
  Copy,
  Check,
  CreditCard,
  ExternalLink,
  Gift,
  Loader2,
  AlertCircle,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useAuth } from "@/components/providers";
import {
  fetchSubscription,
  fetchPaymentHistory,
  activateTrial,
  ApiError,
} from "@/lib/api";
import type { Subscription, Payment } from "@/types";
import { formatDate, formatDateTime, daysUntil } from "@/lib/utils";

function StatusBadge({ status }: { status: string }) {
  if (status === "active")
    return (
      <Badge variant="success" className="gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
        Активна
      </Badge>
    );
  if (status === "trial")
    return (
      <Badge variant="warning" className="gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
        Пробный период
      </Badge>
    );
  return <Badge variant="destructive">Истекла</Badge>;
}

function SubscriptionCard({
  sub,
  onTrialActivate,
  trialUsed,
}: {
  sub: Subscription | null;
  onTrialActivate: () => Promise<void>;
  trialUsed: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [activating, setActivating] = useState(false);
  const [trialError, setTrialError] = useState<string | null>(null);

  const copyUrl = async () => {
    if (!sub?.subscription_url) return;
    await navigator.clipboard.writeText(sub.subscription_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTrial = async () => {
    setActivating(true);
    setTrialError(null);
    try {
      await onTrialActivate();
    } catch (err) {
      if (err instanceof ApiError) {
        setTrialError(err.message);
      } else {
        setTrialError("Ошибка соединения.");
      }
    } finally {
      setActivating(false);
    }
  };

  if (!sub) {
    return (
      <Card className="border-dashed">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted">
              <WifiOff className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Нет активной подписки</CardTitle>
              <CardDescription>Активируйте пробный период или купите план</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {trialError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{trialError}</AlertDescription>
            </Alert>
          )}
        </CardContent>
        <CardFooter className="flex flex-wrap gap-3">
          {!trialUsed && (
            <Button variant="outline" onClick={handleTrial} disabled={activating} className="gap-2">
              {activating ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Активация...</>
              ) : (
                <><Gift className="h-4 w-4" /> Пробный период 3 дня</>
              )}
            </Button>
          )}
          <Button asChild className="gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:opacity-90">
            <Link href="/dashboard/payment">
              <CreditCard className="h-4 w-4" /> Купить подписку
            </Link>
          </Button>
        </CardFooter>
      </Card>
    );
  }

  const days = daysUntil(sub.expires_at);
  const isActive = sub.status === "active" || sub.status === "trial";

  return (
    <Card className={isActive ? "border-indigo-200 shadow-sm shadow-indigo-50" : ""}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${isActive ? "bg-indigo-100" : "bg-muted"}`}>
              <Wifi className={`h-5 w-5 ${isActive ? "text-indigo-600" : "text-muted-foreground"}`} />
            </div>
            <div>
              <CardTitle className="text-base">VPN подписка</CardTitle>
              <CardDescription>
                {sub.traffic_limit_gb === 0 ? "Безлимитный трафик" : `${sub.traffic_limit_gb} ГБ трафика`}
              </CardDescription>
            </div>
          </div>
          <StatusBadge status={sub.status} />
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Dates */}
        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Calendar className="h-4 w-4" />
            <span>Активна с {formatDate(sub.started_at)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Clock className="h-4 w-4" />
            <span>Истекает {formatDate(sub.expires_at)}</span>
          </div>
        </div>

        {/* Days left */}
        {isActive && (
          <div className="rounded-xl border bg-muted/30 p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Осталось дней</span>
              <span
                className={`text-2xl font-bold ${
                  days <= 3 ? "text-destructive" : days <= 7 ? "text-amber-600" : "text-indigo-600"
                }`}
              >
                {days}
              </span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full transition-all ${
                  days <= 3 ? "bg-destructive" : days <= 7 ? "bg-amber-500" : "bg-indigo-500"
                }`}
                style={{ width: `${Math.min(100, (days / 30) * 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Connection URL */}
        <Separator />
        <div className="space-y-2">
          <p className="text-sm font-medium">Конфигурация подключения</p>
          <div className="flex items-center gap-2 rounded-xl border bg-muted/30 p-3">
            <code className="flex-1 truncate text-xs text-muted-foreground">
              {sub.subscription_url}
            </code>
            <Button variant="ghost" size="sm" onClick={copyUrl} className="shrink-0">
              {copied ? (
                <Check className="h-4 w-4 text-emerald-500" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Скопируйте ссылку и вставьте в Hiddify, v2rayNG или другой клиент
          </p>
        </div>
      </CardContent>

      <CardFooter className="flex flex-wrap gap-3">
        <Button asChild className="gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:opacity-90">
          <Link href="/dashboard/payment">
            <CreditCard className="h-4 w-4" /> Продлить
          </Link>
        </Button>
        <Button variant="outline" onClick={copyUrl} className="gap-2">
          {copied ? (
            <><Check className="h-4 w-4 text-emerald-500" /> Скопировано</>
          ) : (
            <><Copy className="h-4 w-4" /> Копировать ссылку</>
          )}
        </Button>
        <Button variant="outline" size="sm" asChild className="gap-2 text-muted-foreground">
          <a href={sub.subscription_url} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-4 w-4" /> Открыть
          </a>
        </Button>
      </CardFooter>
    </Card>
  );
}

const PAYMENT_STATUS_MAP: Record<string, { label: string; variant: "success" | "warning" | "destructive" | "outline" }> = {
  succeeded: { label: "Оплачен", variant: "success" },
  pending:   { label: "Ожидает", variant: "warning" },
  cancelled: { label: "Отменён", variant: "destructive" },
};

function PaymentHistoryTable({ payments }: { payments: Payment[] }) {
  if (payments.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
        <TrendingUp className="h-8 w-8 opacity-30" />
        <p className="text-sm">История платежей пуста</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left">
            <th className="pb-3 pr-4 font-medium text-muted-foreground">Дата</th>
            <th className="pb-3 pr-4 font-medium text-muted-foreground">Тариф</th>
            <th className="pb-3 pr-4 font-medium text-muted-foreground">Сумма</th>
            <th className="pb-3 pr-4 font-medium text-muted-foreground">Метод</th>
            <th className="pb-3 font-medium text-muted-foreground">Статус</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {payments.map((p) => {
            const statusInfo = PAYMENT_STATUS_MAP[p.status];
            return (
              <tr key={p.id} className="hover:bg-muted/30 transition-colors">
                <td className="py-3 pr-4 text-muted-foreground">{formatDateTime(p.created_at)}</td>
                <td className="py-3 pr-4 font-medium">{p.plan_id}</td>
                <td className="py-3 pr-4 font-semibold">{p.amount} {p.currency}</td>
                <td className="py-3 pr-4 capitalize text-muted-foreground">{p.provider}</td>
                <td className="py-3">
                  {statusInfo && (
                    <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [sub, setSub] = useState<Subscription | null | undefined>(undefined);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [paymentsLoading, setPaymentsLoading] = useState(true);
  const [subError, setSubError] = useState<string | null>(null);

  const loadSub = useCallback(async () => {
    try {
      const s = await fetchSubscription();
      setSub(s);
    } catch {
      setSubError("Не удалось загрузить данные подписки.");
      setSub(null);
    }
  }, []);

  useEffect(() => {
    loadSub();
    fetchPaymentHistory()
      .then(setPayments)
      .catch(() => {})
      .finally(() => setPaymentsLoading(false));
  }, [loadSub]);

  const handleTrialActivate = async () => {
    const result = await activateTrial();
    if (!result.ok) {
      const msg =
        result.error === "trial_already_used"
          ? "Пробный период уже был активирован."
          : result.error === "has_active_sub"
          ? "У вас уже есть активная подписка."
          : result.error === "no_servers"
          ? "Нет доступных серверов. Обратитесь в поддержку."
          : "Не удалось активировать пробный период.";
      throw new ApiError(400, msg);
    }
    await loadSub();
  };

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Личный кабинет</h1>
        <p className="mt-1 text-muted-foreground">
          Привет, <span className="font-medium text-foreground">{user?.full_name}</span>! Управляйте своей VPN-подпиской.
        </p>
      </div>

      {subError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{subError}</AlertDescription>
        </Alert>
      )}

      {/* Subscription */}
      {sub === undefined ? (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <Skeleton className="h-10 w-10 rounded-xl" />
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-36" />
                <Skeleton className="h-3 w-24" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-16 w-full rounded-xl" />
          </CardContent>
        </Card>
      ) : (
        <SubscriptionCard
          sub={sub}
          onTrialActivate={handleTrialActivate}
          trialUsed={user?.trial_used ?? false}
        />
      )}

      {/* Payment history */}
      <div>
        <h2 className="mb-4 text-lg font-semibold tracking-tight">История платежей</h2>
        <Card>
          <CardContent className="pt-6">
            {paymentsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : (
              <PaymentHistoryTable payments={payments} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
