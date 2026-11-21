export function validateAllowlist(input) {
  if (!Array.isArray(input) || input.length < 1 || input.length > 50) throw new Error("allowedDomains must contain 1–50 hostnames");
  const values = [...new Set(input.map((v) => String(v).trim().toLowerCase()))];
  for (const value of values) {
    if (!/^(?:\*\.)?[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(value) || value.includes("..") || value.length > 253) throw new Error("Invalid hostname allowlist entry");
    const host = value.startsWith("*.") ? value.slice(2) : value;
    if (!host.includes(".") || /^(?:localhost|.*\.(?:local|internal|test))$/.test(host)) throw new Error("Unsafe hostname allowlist entry");
  }
  return values;
}
export function validateUrl(value, allowlist) {
  const url = new URL(value);
  if (url.protocol !== "https:" || url.username || url.password) throw new Error("Only credential-free HTTPS URLs are allowed");
  const host = url.hostname.toLowerCase();
  const allowed = allowlist.some((pattern) => pattern.startsWith("*.") ? host.endsWith(pattern.slice(1)) && host !== pattern.slice(2) : host === pattern);
  if (!allowed) throw new Error("URL hostname is not in the session allowlist");
  return url.toString();
}
