/**
 * The user's authorisation as the server knows it now, not as the token froze it.
 *
 * The frontend reads `is_admin` and `permissions` from the JWT, which lives for
 * eight hours. Since #137 the backend reads them from the database on every
 * request, so a revoked permission is refused at once — but the menu kept
 * offering the screen until the next login, and every click answered 403.
 *
 * The session heartbeat already calls `/auth/me` every thirty seconds, and that
 * response carries both fields. It only looked at the status code. This applies
 * the body.
 */
export type Authorisation = { isAdmin: boolean; permissions: number };

export function refreshAuthorisation<U extends Authorisation>(
  user: U,
  me: { is_admin?: unknown; permissions?: unknown },
): U {
  const isAdmin = me.is_admin === true;
  const permissions = typeof me.permissions === "number" ? me.permissions : 0;
  // The same object when nothing changed, so a heartbeat does not re-render
  // the whole tree twice a minute for no reason.
  if (user.isAdmin === isAdmin && user.permissions === permissions) return user;
  return { ...user, isAdmin, permissions };
}
