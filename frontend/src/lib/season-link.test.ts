import { describe, it, expect } from "vitest";
import { isSeasonScoped, withSeason } from "@/lib/season-link";

/**
 * IN-01: open `/?season=B`, press Clasificación, land back on season A — because
 * every link was a bare path and the season only lived in shared storage.
 */
describe("withSeason", () => {
  it("carries the season on a season page", () => {
    expect(withSeason("/clasificacion", 12)).toBe("/clasificacion?season=12");
  });

  it("carries it on nested routes too", () => {
    expect(withSeason("/jornadas/6/alineacion", 12)).toBe("/jornadas/6/alineacion?season=12");
  });

  it("keeps a query that is already there", () => {
    expect(withSeason("/jornadas?vista=lista", 12)).toBe("/jornadas?vista=lista&season=12");
  });

  it("replaces a stale season instead of adding a second one", () => {
    expect(withSeason("/clasificacion?season=7", 12)).toBe("/clasificacion?season=12");
  });

  it("keeps the hash after the query", () => {
    expect(withSeason("/jornadas/6#resultados", 12)).toBe("/jornadas/6?season=12#resultados");
  });

  it("leaves the path alone when there is no season yet", () => {
    expect(withSeason("/clasificacion", null)).toBe("/clasificacion");
    expect(withSeason("/clasificacion", undefined)).toBe("/clasificacion");
  });

  it("leaves routes that belong to no season exactly as they are", () => {
    for (const path of ["/palmares", "/perfil", "/login", "/admin/usuarios", "/admin/backup"]) {
      expect(withSeason(path, 12)).toBe(path);
    }
  });
});

describe("isSeasonScoped", () => {
  it("treats the home page as a season page", () => {
    expect(isSeasonScoped("/")).toBe(true);
  });

  it("never touches an external link", () => {
    expect(isSeasonScoped("https://www.futbolfantasy.com")).toBe(false);
    expect(isSeasonScoped("//cdn.example.com/x")).toBe(false);
    expect(isSeasonScoped("mailto:a@b.c")).toBe(false);
  });

  it("does not mistake a route that merely starts like a global one", () => {
    // "/perfiles" is not "/perfil"
    expect(isSeasonScoped("/perfiles")).toBe(true);
  });
});
