"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldCheck, Loader2, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useAuth } from "@/components/providers";
import {
  authTelegram,
  login,
  register,
  setToken,
  ApiError,
} from "@/lib/api";
import {
  getTelegramInitData,
  initTelegramApp,
  isTelegramWebApp,
} from "@/lib/telegram";

const RECAPTCHA_SITE_KEY = process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY ?? "";

declare global {
  interface Window {
    grecaptcha?: {
      ready(cb: () => void): void;
      execute(siteKey: string, options: { action: string }): Promise<string>;
    };
  }
}

async function getRecaptchaToken(): Promise<string> {
  if (!RECAPTCHA_SITE_KEY) return "no-captcha-configured";
  return new Promise((resolve, reject) => {
    window.grecaptcha?.ready(async () => {
      try {
        const token = await window.grecaptcha!.execute(RECAPTCHA_SITE_KEY, {
          action: "register",
        });
        resolve(token);
      } catch (e) {
        reject(e);
      }
    });
  });
}

type Mode = "login" | "register";

function AuthContent() {
  const { user, loading, refresh } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectPlan = searchParams.get("plan");

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [tgLoading, setTgLoading] = useState(false);

  const handleSuccess = useCallback(
    async (token: string) => {
      setToken(token);
      await refresh();
      const dest = redirectPlan ? `/dashboard/payment?plan=${redirectPlan}` : "/dashboard";
      router.push(dest);
    },
    [refresh, router, redirectPlan],
  );

  useEffect(() => {
    if (loading || user) return;
    if (!isTelegramWebApp()) return;
    initTelegramApp();
    const initData = getTelegramInitData();
    if (!initData) return;
    setTgLoading(true);
    authTelegram(initData)
      .then(handleSuccess)
      .catch(() => {
        setTgLoading(false);
        setError("Не удалось авторизоваться через Telegram. Попробуйте войти с email.");
      });
  }, [loading, user, handleSuccess]);

  useEffect(() => {
    if (!loading && user) {
      const dest = redirectPlan ? `/dashboard/payment?plan=${redirectPlan}` : "/dashboard";
      router.push(dest);
    }
  }, [user, loading, router, redirectPlan]);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      let token: string;
      if (mode === "login") {
        token = await login(email, password);
      } else {
        const recaptchaToken = await getRecaptchaToken().catch(() => "");
        token = await register({
          email,
          password,
          full_name: fullName,
          recaptcha_token: recaptchaToken,
        });
      }
      await handleSuccess(token);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) setError("Email уже зарегистрирован.");
        else if (err.status === 401) setError("Неверный email или пароль.");
        else if (err.status === 400) setError("Проверка reCAPTCHA не пройдена. Попробуйте ещё раз.");
        else setError(err.message);
      } else {
        setError("Ошибка соединения. Проверьте интернет и попробуйте снова.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || tgLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-violet-50">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
          <p className="text-sm">
            {tgLoading ? "Авторизация через Telegram..." : "Загрузка..."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-violet-50/50 p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-200">
            <ShieldCheck className="h-7 w-7 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">VPNBox</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {mode === "login" ? "Войдите в свой аккаунт" : "Создайте аккаунт бесплатно"}
            </p>
          </div>
        </div>

        <Card className="border shadow-sm">
          <CardHeader className="pb-2 pt-5">
            {/* Tab switcher */}
            <div className="flex rounded-xl bg-muted p-1">
              <button
                className={`flex-1 rounded-lg py-2 text-sm font-medium transition-all ${
                  mode === "login"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => { setMode("login"); setError(null); }}
              >
                Войти
              </button>
              <button
                className={`flex-1 rounded-lg py-2 text-sm font-medium transition-all ${
                  mode === "register"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => { setMode("register"); setError(null); }}
              >
                Регистрация
              </button>
            </div>
          </CardHeader>

          <CardContent className="pb-6">
            <form onSubmit={handleEmailSubmit} className="space-y-4">
              {mode === "register" && (
                <div className="space-y-1.5">
                  <Label htmlFor="fullName">Имя</Label>
                  <Input
                    id="fullName"
                    placeholder="Иван Иванов"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                    disabled={submitting}
                  />
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={submitting}
                  autoComplete={mode === "login" ? "email" : "off"}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">Пароль</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder={mode === "register" ? "Минимум 8 символов" : "Ваш пароль"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={submitting}
                    autoComplete={mode === "login" ? "current-password" : "new-password"}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <Button
                type="submit"
                className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 hover:opacity-90"
                disabled={submitting}
              >
                {submitting ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Подождите...</>
                ) : mode === "login" ? (
                  "Войти"
                ) : (
                  "Создать аккаунт"
                )}
              </Button>

              {mode === "register" && (
                <p className="text-center text-xs text-muted-foreground">
                  Регистрируясь, вы соглашаетесь с{" "}
                  <a href="#" className="underline hover:text-foreground">условиями использования</a>
                  {" "}и{" "}
                  <a href="#" className="underline hover:text-foreground">политикой конфиденциальности</a>.
                </p>
              )}
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-muted-foreground">
          Используете Telegram Mini App?{" "}
          <span className="font-medium text-foreground">Авторизация автоматическая.</span>
        </p>
      </div>

      {RECAPTCHA_SITE_KEY && mode === "register" && (
        <script
          src={`https://www.google.com/recaptcha/api.js?render=${RECAPTCHA_SITE_KEY}`}
          async
          defer
        />
      )}
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-violet-50">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
        </div>
      }
    >
      <AuthContent />
    </Suspense>
  );
}
