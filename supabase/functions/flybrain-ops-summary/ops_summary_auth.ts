export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function parseOwnerAllowlist(raw: string | null): Set<string> | null {
  if (!raw || !raw.trim()) return null;
  const entries = raw.split(",").map((value) => value.trim().toLowerCase());
  if (entries.length === 0 || entries.some((value) => !UUID_RE.test(value))) {
    throw new Error("invalid_owner_allowlist_configuration");
  }
  return new Set(entries);
}

export function isOwnerAllowed(userId: unknown, allowlist: Set<string> | null): boolean {
  return typeof userId === "string" && UUID_RE.test(userId) &&
    allowlist !== null && allowlist.has(userId.toLowerCase());
}

export function isOriginAllowed(origin: string | null, configuredOrigin: string | null): boolean {
  if (origin === null) return true; // non-browser clients still require a valid user JWT
  if (!configuredOrigin) return false;
  try {
    const actual = new URL(origin);
    const expected = new URL(configuredOrigin);
    return actual.origin === origin && expected.origin === configuredOrigin &&
      actual.origin === expected.origin && actual.protocol === "https:";
  } catch {
    return false;
  }
}
