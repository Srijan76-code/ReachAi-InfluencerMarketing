import { countries } from "@/data/countries";

/** Every country in the picker has a flag emoji; a flag is two "regional indicator" letters,
 * which spell the ISO 3166 alpha-2 code (🇺🇸 = U + S). */
export function flagToCode(flag: string): string | null {
  const points = Array.from(flag).map((c) => c.codePointAt(0) ?? 0);
  if (points.length !== 2) return null;
  const A = 0x1f1e6;
  if (points.some((p) => p < A || p > A + 25)) return null;
  return points.map((p) => String.fromCharCode(p - A + 65)).join("");
}

const all = countries.flatMap((group) => group.items);
const byName = new Map(all.map((c) => [c.value.toLowerCase(), flagToCode(c.flag)]));
const byCode = new Map(all.map((c) => [flagToCode(c.flag), c.value]));

/** "United States" -> "US". Also accepts a code ("us" -> "US"). Unknown -> null (never a guess). */
export function countryCode(nameOrCode: string | null | undefined): string | null {
  if (!nameOrCode) return null;
  const v = nameOrCode.trim();
  const fromName = byName.get(v.toLowerCase());
  if (fromName) return fromName;
  const upper = v.toUpperCase();
  return byCode.has(upper) ? upper : null;
}

/** "US" -> "United States". Accepts a name too, so saved briefs in either form load back. */
export function countryName(codeOrName: string | null | undefined): string {
  if (!codeOrName) return "";
  const code = countryCode(codeOrName);
  return (code && byCode.get(code)) || "";
}

// Main local language for countries where many creators don't post in English. English is
// always included; the creator's language check uses this list.
const LOCAL_LANGUAGE: Record<string, string> = {
  IN: "hi", PK: "ur", BD: "bn", FR: "fr", BE: "fr", DE: "de", AT: "de", CH: "de", ES: "es", MX: "es",
  AR: "es", CO: "es", CL: "es", PE: "es", VE: "es", BR: "pt", PT: "pt", IT: "it", NL: "nl", JP: "ja",
  KR: "ko", CN: "zh", TW: "zh", RU: "ru", UA: "uk", PL: "pl", TR: "tr", ID: "id", VN: "vi", TH: "th",
  SA: "ar", AE: "ar", EG: "ar", SE: "sv", NO: "no", DK: "da", FI: "fi", GR: "el", IL: "he", IR: "fa",
};

export function languagesFor(code: string | null): string[] {
  const local = code ? LOCAL_LANGUAGE[code] : undefined;
  return local ? ["en", local] : ["en"];
}
