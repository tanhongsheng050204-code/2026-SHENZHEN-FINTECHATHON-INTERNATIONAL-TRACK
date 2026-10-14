import type { Lang } from "./i18n";

/** The locale for formatting dates in a language. */
export function dateLocale(lang: Lang): string {
  return lang === "zh" ? "zh-CN" : lang === "ms" ? "ms-MY" : "en-GB";
}
