/**
 * Clerk appends query params while finishing OAuth / dev DB session sync.
 * If we redirect to `/login` before that completes, we strip the handshake and
 * cause an infinite bounce between localhost and `*.accounts.dev`.
 */
const CLERK_HANDSHAKE_PARAMS = [
  "__clerk_db_jwt",
  "__clerk_status",
  "__clerk_created_session",
  "__clerk_ticket",
  "__clerk_redirect_url",
] as const;

export function isClerkHandshakeSearch(search: string): boolean {
  const normalized = search.startsWith("?") ? search.slice(1) : search;
  if (!normalized) return false;
  const params = new URLSearchParams(normalized);
  return CLERK_HANDSHAKE_PARAMS.some((key) => params.has(key));
}
