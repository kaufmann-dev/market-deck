import type { ListInfo } from "./api/types";
import { normalizeTag, sortedTags } from "./stores/app.svelte";

export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return (value >= 0 ? "+" : "") + value.toFixed(2) + "%";
}

export function retTextColor(value: number | null | undefined): string {
  if (!value && value !== 0) return "#718096";
  return value >= 0 ? "#68d391" : "#fc8181";
}

export function retBgColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "#4a5568";
  if (value > 4) return "#38a169";
  if (value > 2) return "#68d391";
  if (value > 0) return "#9ae6b4";
  if (value > -2) return "#fc8181";
  if (value > -4) return "#e53e3e";
  return "#9b2c2c";
}

export function currencySymbol(currency: string): string {
  try {
    const formatter = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
    return formatter.format(0).replace(/\d/g, "").trim();
  } catch {
    return currency;
  }
}

export function formatMoney(value: number | null | undefined, currency = "USD"): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: value >= 100 ? 0 : 2,
    }).format(value);
  } catch {
    return `${currency} ${value.toFixed(2)}`;
  }
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatLargeNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatUnixDate(value: number | null | undefined): string {
  if (!value) return "";
  return new Date(value * 1000).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function tagStyle(tag: string, list: ListInfo | null): string {
  const info = sortedTags(list).find((item) => item.tag === normalizeTag(tag));
  if (info) return `background:${info.bg};color:${info.text};border:1px solid ${info.border}`;
  return "background:rgba(160, 174, 192, 0.1);color:#a0aec0;border:1px solid rgba(160, 174, 192, 0.25)";
}

export function formatBaseDate(isoDate: string): string {
  return new Date(isoDate + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

/** From a single hex color, generate bg (12% opacity), text (full), border (30% opacity). */
export function autoTagColors(hex: string): { bg: string; text: string; border: string } {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return {
    bg: `rgba(${r},${g},${b},0.12)`,
    text: hex,
    border: `rgba(${r},${g},${b},0.30)`,
  };
}

export function hexFromTagColors(colors: { text: string }): string {
  if (colors.text?.startsWith("#")) return colors.text;
  const match = colors.text?.match(/(\d+),\s*(\d+),\s*(\d+)/);
  if (match) {
    const toHex = (n: string) => parseInt(n).toString(16).padStart(2, "0");
    return `#${toHex(match[1])}${toHex(match[2])}${toHex(match[3])}`;
  }
  return "#68d391";
}
