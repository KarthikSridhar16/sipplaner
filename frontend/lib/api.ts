export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : `The request could not be completed (${response.status}).`);
  }
  return response.json();
}
export function fmt(value: number | null | undefined, digits = 2) {
  return value == null ? "—" : value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
export function dateLabel(value: string | null | undefined) {
  if (!value) return "Not supplied";
  return new Date(value).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
