"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, ShieldCheck, Zap, Globe, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { fetchPlans } from "@/lib/api";
import type { Plan } from "@/types";
import { useAuth } from "@/components/providers";
import { useRouter } from "next/navigation";

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Максимальная защита",
    description: "VLESS + REALITY протокол. Невозможно заблокировать или обнаружить.",
    color: "bg-indigo-100 text-indigo-600",
  },
  {
    icon: Zap,
    title: "Высокая скорость",
    description: "Выделенные серверы без перегрузки. Пинг от 10 мс.",
    color: "bg-amber-100 text-amber-600",
  },
  {
    icon: Globe,
    title: "Без ограничений",
    description: "Полный доступ к любым ресурсам. Безлимитный трафик в топовых тарифах.",
    color: "bg-emerald-100 text-emerald-600",
  },
  {
    icon: EyeOff,
    title: "Нет логов",
    description: "Мы не храним данные о вашей активности. Приватность по умолчанию.",
    color: "bg-violet-100 text-violet-600",
  },
];

export default function LandingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);

  useEffect(() => {
    fetchPlans()
      .then(setPlans)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!loading && user) {
      router.push("/dashboard");
    }
  }, [user, loading, router]);

  return (
    <div className="min-h-screen bg-background">
      {/* Navbar */}
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
              <ShieldCheck className="h-4 w-4 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight">VPNBox</span>
          </div>
          <nav className="flex items-center gap-2">
            {user ? (
              <Button asChild>
                <Link href="/dashboard">Dashboard</Link>
              </Button>
            ) : (
              <>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/auth">Войти</Link>
                </Button>
                <Button size="sm" asChild>
                  <Link href="/auth">Начать бесплатно</Link>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="hero-gradient relative overflow-hidden">
          <div className="container py-28 text-center md:py-36">
            <div className="mx-auto max-w-3xl space-y-8">
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-4 py-1.5 text-sm font-medium text-indigo-700">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-500" />
                </span>
                Моментальная активация · Без регистрации через Telegram
              </div>

              <h1 className="text-5xl font-bold tracking-tight md:text-7xl">
                Быстрый и{" "}
                <span className="gradient-text">безопасный VPN</span>
              </h1>

              <p className="text-lg text-muted-foreground md:text-xl">
                Полная приватность в интернете. Работает везде — Windows, macOS, iOS, Android.
                <br />
                Подключение за 60 секунд.
              </p>

              <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
                <Button size="lg" className="gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 shadow-lg shadow-indigo-200 hover:shadow-indigo-300 hover:opacity-90" asChild>
                  <Link href="/auth">
                    Начать бесплатно <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" asChild>
                  <Link href="#pricing">Посмотреть тарифы</Link>
                </Button>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-6 pt-4 text-sm text-muted-foreground">
                {["Пробный период 3 дня", "Карта не нужна", "Отмена в любой момент"].map((item) => (
                  <div key={item} className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <Separator />

        {/* Features */}
        <section className="container py-24">
          <div className="mb-14 text-center">
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">Почему VPNBox?</h2>
            <p className="mt-3 text-muted-foreground">
              Современный протокол, честные цены, без рекламы
            </p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <Card key={f.title} className="card-hover border bg-card shadow-sm">
                <CardHeader>
                  <div className={`mb-3 flex h-11 w-11 items-center justify-center rounded-xl ${f.color}`}>
                    <f.icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-base font-semibold">{f.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground leading-relaxed">{f.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <Separator />

        {/* Pricing */}
        <section id="pricing" className="container py-24">
          <div className="mb-14 text-center">
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">Тарифы</h2>
            <p className="mt-3 text-muted-foreground">Прозрачная цена без скрытых платежей</p>
          </div>

          {plans.length === 0 ? (
            <div className="flex justify-center gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-72 w-60 animate-pulse rounded-2xl bg-muted" />
              ))}
            </div>
          ) : (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {plans.map((plan, idx) => {
                const isPopular = idx === 1;
                return (
                  <div
                    key={plan.id}
                    className={`relative rounded-2xl border p-6 transition-all ${
                      isPopular
                        ? "border-indigo-300 bg-gradient-to-b from-indigo-50 to-white shadow-lg shadow-indigo-100"
                        : "bg-card shadow-sm hover:shadow-md"
                    }`}
                  >
                    {isPopular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                        <span className="rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 px-3 py-1 text-xs font-semibold text-white shadow-sm">
                          Популярный
                        </span>
                      </div>
                    )}

                    <div className="space-y-4">
                      <div>
                        <p className="font-semibold text-base">{plan.name}</p>
                        <div className="mt-2 flex items-baseline gap-1">
                          <span className="text-4xl font-bold">{plan.price}</span>
                          <span className="text-muted-foreground">₽</span>
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">{plan.description}</p>
                      </div>

                      <Separator />

                      <ul className="space-y-2.5">
                        {[
                          `${plan.duration_days} дней доступа`,
                          plan.traffic_gb === 0 ? "Безлимитный трафик" : `${plan.traffic_gb} ГБ трафика`,
                          "Все устройства",
                          "Поддержка 24/7",
                        ].map((item) => (
                          <li key={item} className="flex items-center gap-2 text-sm">
                            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                            {item}
                          </li>
                        ))}
                      </ul>

                      <Button
                        className={`w-full ${isPopular ? "bg-gradient-to-r from-indigo-600 to-violet-600 hover:opacity-90" : ""}`}
                        variant={isPopular ? "default" : "outline"}
                        asChild
                      >
                        <Link href={`/auth?plan=${plan.id}`}>Выбрать план</Link>
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* CTA */}
        <section className="relative overflow-hidden bg-gradient-to-br from-indigo-600 via-violet-600 to-purple-700 py-24 text-white">
          <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PHBhdGggZD0iTTM2IDM0djZoNnYtNmgtNnptNiA2djZoNnYtNmgtNnptLTEyIDBoNnY2aC02di02em0tNiA2djZoNnYtNmgtNnoiLz48L2c+PC9nPjwvc3ZnPg==')] opacity-40" />
          <div className="container relative text-center">
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
              Начните прямо сейчас
            </h2>
            <p className="mt-4 text-lg text-white/80">
              Пробный период 3 дня — бесплатно. Карта не нужна.
            </p>
            <Button
              size="lg"
              variant="secondary"
              className="mt-8 bg-white text-indigo-700 shadow-xl hover:bg-white/90"
              asChild
            >
              <Link href="/auth">Попробовать бесплатно</Link>
            </Button>
          </div>
        </section>
      </main>

      <footer className="border-t bg-muted/30 py-10">
        <div className="container flex flex-col items-center gap-4 text-sm text-muted-foreground sm:flex-row sm:justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-indigo-500 to-violet-600">
              <ShieldCheck className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="font-medium text-foreground">VPNBox</span>
            <span>© {new Date().getFullYear()}</span>
          </div>
          <div className="flex gap-6">
            <a href="#" className="hover:text-foreground transition-colors">Политика конфиденциальности</a>
            <a href="#" className="hover:text-foreground transition-colors">Условия использования</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
