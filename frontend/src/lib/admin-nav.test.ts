import { describe, it, expect } from "vitest";
import { PERM } from "@/lib/permissions";
import {
  ADMIN_ITEMS,
  ROUTE_PERM,
  canSeeAdminItem,
  seasonItems,
  operationsItems,
  systemItems,
  adminLabelForPath,
  resolveCompetitionContexts,
} from "@/lib/admin-nav";

const item = (href: string) => ADMIN_ITEMS.find((i) => i.href === href)!;

describe("canSeeAdminItem", () => {
  it("admin sees every item", () => {
    for (const it_ of ADMIN_ITEMS) {
      expect(canSeeAdminItem(true, 0, it_)).toBe(true);
    }
  });

  it("a delegate with only STATS sees Estadísticas and Predicciones, nothing else", () => {
    const perms = PERM.STATS;
    const visible = ADMIN_ITEMS.filter((i) => canSeeAdminItem(false, perms, i)).map(
      (i) => i.href,
    );
    expect(visible.sort()).toEqual(["/admin/estadisticas", "/admin/predicciones"].sort());
  });

  it("hides null-perm (super-admin) items from non-admins", () => {
    expect(canSeeAdminItem(false, 0xffff, item("/admin/temporadas"))).toBe(false);
    expect(canSeeAdminItem(false, 0xffff, item("/plantillas"))).toBe(false);
  });
});

describe("seasonItems", () => {
  it("league includes Logros and excludes Grupos", () => {
    const hrefs = seasonItems("league").map((i) => i.href);
    expect(hrefs).toContain("/admin/logros");
    expect(hrefs).not.toContain("/admin/grupos");
  });

  it("tournament includes Grupos and excludes Logros", () => {
    const hrefs = seasonItems("tournament").map((i) => i.href);
    expect(hrefs).toContain("/admin/grupos");
    expect(hrefs).not.toContain("/admin/logros");
  });

  it("Draft and Plantillas are season-scoped", () => {
    const hrefs = seasonItems("league").map((i) => i.href);
    expect(hrefs).toContain("/drafts/gestionar");
    expect(hrefs).toContain("/plantillas");
  });
});

describe("scope buckets", () => {
  it("operations = Scraping + Telegram", () => {
    expect(operationsItems.map((i) => i.href).sort()).toEqual(
      ["/admin/scraping", "/admin/telegram"].sort(),
    );
  });

  it("system = Temporadas, Usuarios, Invitaciones, Backup (all super-admin)", () => {
    expect(systemItems.every((i) => i.perm === null)).toBe(true);
    expect(systemItems.map((i) => i.href)).toContain("/admin/backup");
  });
});

describe("resolveCompetitionContexts", () => {
  const liga = { id: 12, name: "Liga", kind: "league" };
  const mundial = { id: 9, name: "Mundial", kind: "tournament" };

  it("falls back to the selected league when nothing is active", () => {
    const { league, tournament } = resolveCompetitionContexts(null, null, liga);
    expect(league).toBe(liga);
    expect(tournament).toBeNull();
  });

  it("falls back to the selected tournament when nothing is active", () => {
    const { league, tournament } = resolveCompetitionContexts(null, null, mundial);
    expect(tournament).toBe(mundial);
    expect(league).toBeNull();
  });

  it("prefers active competitions over the selection", () => {
    const active = { id: 1, name: "Liga activa", kind: "league" };
    const { league } = resolveCompetitionContexts(active, null, liga);
    expect(league).toBe(active);
  });

  it("treats a missing kind as league", () => {
    const noKind: { id: number; name: string; kind?: string | null } = { id: 5, name: "X" };
    const { league } = resolveCompetitionContexts(null, null, noKind);
    expect(league?.id).toBe(5);
  });
});

describe("ROUTE_PERM + labels", () => {
  it("ROUTE_PERM covers every item and matches its perm", () => {
    for (const it_ of ADMIN_ITEMS) {
      expect(ROUTE_PERM[it_.href]).toBe(it_.perm);
    }
  });

  it("adminLabelForPath matches nested routes", () => {
    expect(adminLabelForPath("/admin/estadisticas/foo")).toBe("Estadísticas");
    expect(adminLabelForPath("/unknown")).toBe("Admin");
  });
});
