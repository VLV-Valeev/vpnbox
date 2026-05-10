/**
 * Telegram WebApp utilities.
 * Works both in Telegram Mini App context and regular browser.
 */

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: {
      id: number;
      first_name: string;
      last_name?: string;
      username?: string;
      language_code?: string;
    };
    start_param?: string;
    auth_date: number;
    hash: string;
  };
  ready(): void;
  expand(): void;
  close(): void;
  MainButton: {
    text: string;
    isVisible: boolean;
    show(): void;
    hide(): void;
    onClick(fn: () => void): void;
  };
  BackButton: {
    isVisible: boolean;
    show(): void;
    hide(): void;
    onClick(fn: () => void): void;
  };
  colorScheme: "light" | "dark";
  themeParams: {
    bg_color?: string;
    text_color?: string;
    hint_color?: string;
    link_color?: string;
    button_color?: string;
    button_text_color?: string;
  };
}

export function isTelegramWebApp(): boolean {
  return (
    typeof window !== "undefined" &&
    Boolean(window.Telegram?.WebApp?.initData)
  );
}

export function getTelegramWebApp(): TelegramWebApp | null {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp ?? null;
}

export function getTelegramInitData(): string | null {
  const twa = getTelegramWebApp();
  return twa?.initData || null;
}

export function getTelegramUser() {
  const twa = getTelegramWebApp();
  return twa?.initDataUnsafe?.user ?? null;
}

export function initTelegramApp(): void {
  const twa = getTelegramWebApp();
  if (twa) {
    twa.ready();
    twa.expand();
  }
}
