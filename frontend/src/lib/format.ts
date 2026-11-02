export function formatDate(value: string | null | undefined, fallback = "—"): string {
  if (!value) return fallback;
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const date = dateOnly
    ? new Date(Number(value.slice(0, 4)), Number(value.slice(5, 7)) - 1, Number(value.slice(8, 10)))
    : new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function money(value: string | number | null | undefined, currency = "NGN"): string {
  const amount = Number(value ?? 0);
  if (Number.isNaN(amount)) return "—";
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    maximumFractionDigits: 2,
  }).format(amount);
}

export function compactMoney(value: string | number | null | undefined): string {
  const amount = Number(value ?? 0);
  if (Number.isNaN(amount)) return "—";
  return new Intl.NumberFormat("en-NG", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(amount);
}

export function count(value: number | null | undefined): string {
  return new Intl.NumberFormat("en-GB").format(value ?? 0);
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function todayLabel(): string {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date());
}

export function toneForState(value: string): "ok" | "warn" | "danger" | "neutral" {
  if (["confirmed", "attended", "paid", "approved", "posted", "completed"].includes(value)) {
    return "ok";
  }
  if (["cancelled", "rejected", "void", "failed", "overflow", "expired", "unfit"].includes(value)) {
    return "danger";
  }
  if (
    ["registered", "payment_uploaded", "pending", "part_paid", "draft", "expiring_soon"].includes(
      value,
    )
  ) {
    return "warn";
  }
  return "neutral";
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Something went wrong. Try again.";
}

export function detailFor(error: unknown, field: string): string | undefined {
  if (!error || typeof error !== "object" || !("details" in error)) return undefined;
  const details = (error as { details?: Record<string, string[]> }).details;
  return details?.[field]?.[0];
}
