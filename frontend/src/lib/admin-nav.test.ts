import { describe, it, expect } from "vitest";
import { PERM } from "@/lib/permissions";
import {
  ADMIN_ITEMS,
  ROUTE_PERM,
  canSeeAdminItem,
  hrefForSeason,
  seasonItems,
  operationsItems,
  systemItems,
  adminLabelForPath,
  resolveCompetitionContexts,
  seasonNotice,
  visibleAdminItems,
} from "@/lib/admin-nav";

const item = (href: string) => ADMIN_ITEMS.find((i) => i.href === href)!;

describe("canSeeAdminItem", () => {
  it("admin sees every item", () => {
    for (const it_ of ADMIN_ITEMS) {
      expect(canSeeAdminItem(true, 0, it_)).toBe(true);
    }
  });

  it("a delegate with only STATS sees no analytics: it is the creator's alone", () => {
    const perms = PERM.STATS;
    const visible = ADMIN_ITEMS.filter((i) => canSeeAdminItem(false, perms, i)).map(
      (i) => i.href,
    );
    expect(visible).not.toContain("/admin/estadisticas");
    expect(visible).not.toContain("/admin/predicciones");
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

  it("from a historical league, the league section is that season, not the active one", () => {
    // It used to prefer the active season, so every rail link from 2023-24
    // carried the id of 2026-27 while the banner said 2023-24.
    const active = { id: 12, name: "Liga activa", kind: "league" };
    const historica = { id: 7, name: "2023-24", kind: "league" };
    const { league } = resolveCompetitionContexts(active, null, historica);
    expect(league).toBe(historica);
  });

  it("the other competition still falls back to its active season", () => {
    const active = { id: 12, name: "Liga activa", kind: "league" };
    const { league, tournament } = resolveCompetitionContexts(active, mundial, mundial);
    expect(tournament).toBe(mundial);
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

describe("hrefForSeason", () => {
  const jornadas = item("/admin/jornadas");

  it("makes the Liga and Torneo links genuinely different", () => {
    // Both sections are built from the same ADMIN_ITEMS, so without the season
    // these were the same href and the page picked a season of its own.
    expect(hrefForSeason(jornadas, 12)).not.toBe(hrefForSeason(jornadas, 13));
  });

  it("stamps the season on every season-scoped item of both competitions", () => {
    for (const kind of ["league", "tournament"] as const) {
      for (const i of seasonItems(kind)) {
        expect(hrefForSeason(i, 12)).toContain("season=12");
      }
    }
  });

  it("leaves the route itself untouched, so highlighting still matches", () => {
    expect(hrefForSeason(jornadas, 12).startsWith(jornadas.href)).toBe(true);
  });

  it("returns the plain href for items with no season (Operaciones, Sistema)", () => {
    for (const i of [...operationsItems, ...systemItems]) {
      expect(hrefForSeason(i, null)).toBe(i.href);
      expect(hrefForSeason(i, undefined)).toBe(i.href);
    }
  });

  it("appends rather than replaces when the href already carries a query", () => {
    const withQuery = { ...jornadas, href: "/admin/jornadas?tab=pendientes" };
    expect(hrefForSeason(withQuery, 12)).toBe("/admin/jornadas?tab=pendientes&season=12");
  });
});

describe("visibleAdminItems — one rule for the rail and the admin home", () => {
  const hrefs = (items: { href: string }[]) => items.map((i) => i.href);

  it("offers Logros but not Grupos in a league", () => {
    const got = hrefs(visibleAdminItems(true, 0, { kind: "league" }));
    expect(got).toContain("/admin/logros");
    expect(got).not.toContain("/admin/grupos");
  });

  it("offers Grupos but not Logros in a tournament", () => {
    const got = hrefs(visibleAdminItems(true, 0, { kind: "tournament" }));
    expect(got).toContain("/admin/grupos");
    expect(got).not.toContain("/admin/logros");
  });

  it("drops Economía in a season without weekly payments, keeps it otherwise", () => {
    expect(hrefs(visibleAdminItems(true, 0, { weekly_payments_enabled: false }))).not.toContain(
      "/admin/economia",
    );
    expect(hrefs(visibleAdminItems(true, 0, { weekly_payments_enabled: true }))).toContain(
      "/admin/economia",
    );
    expect(hrefs(visibleAdminItems(true, 0, {}))).toContain("/admin/economia");
  });

  it("still filters by permission: a matchdays delegate gets Jornadas and no Sistema", () => {
    const got = visibleAdminItems(false, PERM.MATCHDAYS, { kind: "league" });
    expect(hrefs(got)).toContain("/admin/jornadas");
    expect(got.some((i) => i.scope === "system")).toBe(false);
  });

  it("reads a missing season as a league", () => {
    expect(hrefs(visibleAdminItems(true, 0, null))).toContain("/admin/logros");
  });
});

describe("seasonNotice", () => {
  it("says a season in preparation is in preparation, not historical", () => {
    const notice = seasonNotice({ name: "2027-2028", status: "setup" });
    expect(notice?.tone).toBe("info");
    expect(notice?.text).toContain("preparación");
    expect(notice?.text).not.toContain("históricos");
  });

  it("warns that a closed season is historical data", () => {
    const notice = seasonNotice({ name: "2023-2024", status: "finished" });
    expect(notice?.tone).toBe("warning");
    expect(notice?.text).toContain("históricos");
  });

  it("says nothing about the active season, or when there is none", () => {
    expect(seasonNotice({ name: "2026-2027", status: "active" })).toBeNull();
    expect(seasonNotice(null)).toBeNull();
  });
});
