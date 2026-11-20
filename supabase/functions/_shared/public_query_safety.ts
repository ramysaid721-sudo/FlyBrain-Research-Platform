const PUBLIC_QUERY_SENSITIVE_PATTERNS: RegExp[] = [
  /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i,
  /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/,
  /\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/,
  /\bsk-[A-Za-z0-9_-]{20,}\b/,
  /\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b/,
  /\bAIza[0-9A-Za-z_-]{35}\b/,
  /\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/,
  /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/,
  /\bglpat-[A-Za-z0-9_-]{20,}\b/,
  /\bnpm_[A-Za-z0-9]{36}\b/,
  /\bBearer\s+[A-Za-z0-9._~+/-]{20,}={0,}\b/i,
  /\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b/,
  /(?:password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*\S+/i
];

export function assertPublicExternalQuery(query: string): void {
  if (PUBLIC_QUERY_SENSITIVE_PATTERNS.some((pattern) => pattern.test(query))) {
    throw new Error("query_blocked_by_external_data_safety_policy");
  }
}
