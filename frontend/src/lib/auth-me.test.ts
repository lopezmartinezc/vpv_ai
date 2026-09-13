import { describe, it, expect } from "vitest";
import { refreshAuthorisation } from "@/lib/auth-me";

const user = { id: "7", username: "ana", displayName: "ana", isAdmin: false, permissions: 64 };

describe("refreshAuthorisation", () => {
  it("drops a revoked permission straight away", () => {
    expect(refreshAuthorisation(user, { is_admin: false, permissions: 0 }).permissions).toBe(0);
  });

  it("drops a revoked administrator straight away", () => {
    const admin = { ...user, isAdmin: true };
    expect(refreshAuthorisation(admin, { is_admin: false, permissions: 64 }).isAdmin).toBe(false);
  });

  it("applies a newly granted permission without a new login", () => {
    expect(refreshAuthorisation(user, { is_admin: false, permissions: 64 | 16 }).permissions).toBe(80);
  });

  it("keeps the same object when nothing changed, so nothing re-renders", () => {
    expect(refreshAuthorisation(user, { is_admin: false, permissions: 64 })).toBe(user);
  });

  it("keeps identity and display fields untouched", () => {
    const next = refreshAuthorisation(user, { is_admin: true, permissions: 0 });
    expect(next).toMatchObject({ id: "7", username: "ana", displayName: "ana" });
  });

  it("reads a malformed body as no privileges rather than keeping old ones", () => {
    const admin = { ...user, isAdmin: true };
    expect(refreshAuthorisation(admin, {})).toMatchObject({ isAdmin: false, permissions: 0 });
  });
});
