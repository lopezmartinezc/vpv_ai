import { describe, expect, it } from "vitest";

import { UNTAGGED, matchesTagFilter, tagCounts, toggleTag } from "./draft-tag-filter";

describe("matchesTagFilter", () => {
  it("shows everyone when nothing is selected", () => {
    expect(matchesTagFilter(["titular"], [])).toBe(true);
    expect(matchesTagFilter([], [])).toBe(true);
  });

  it("reads several tags as OR — the two lists, not their intersection", () => {
    expect(matchesTagFilter(["objetivo"], ["objetivo", "duda"])).toBe(true);
    expect(matchesTagFilter(["duda"], ["objetivo", "duda"])).toBe(true);
    expect(matchesTagFilter(["lesion"], ["objetivo", "duda"])).toBe(false);
  });

  it("keeps a player who carries the tag among others", () => {
    expect(matchesTagFilter(["rotacion", "penaltis"], ["penaltis"])).toBe(true);
  });

  it("finds the players still to review", () => {
    expect(matchesTagFilter([], [UNTAGGED])).toBe(true);
    expect(matchesTagFilter(["titular"], [UNTAGGED])).toBe(false);
  });

  it("treats a missing tag list as untagged, not as an error", () => {
    expect(matchesTagFilter(null, [UNTAGGED])).toBe(true);
    expect(matchesTagFilter(undefined, [UNTAGGED])).toBe(true);
    expect(matchesTagFilter(undefined, ["titular"])).toBe(false);
  });

  it("combines untagged with a tag as OR, so both groups show", () => {
    expect(matchesTagFilter([], [UNTAGGED, "titular"])).toBe(true);
    expect(matchesTagFilter(["titular"], [UNTAGGED, "titular"])).toBe(true);
    expect(matchesTagFilter(["lesion"], [UNTAGGED, "titular"])).toBe(false);
  });
});

describe("tagCounts", () => {
  const players = [
    { tags: ["titular", "penaltis"] },
    { tags: ["titular"] },
    { tags: [] },
    { tags: null },
    {},
  ];

  it("counts each tag across the board", () => {
    const counts = tagCounts(players);
    expect(counts.titular).toBe(2);
    expect(counts.penaltis).toBe(1);
  });

  it("counts what is left to review, however the absence is expressed", () => {
    expect(tagCounts(players)[UNTAGGED]).toBe(3);
  });

  it("counts a duplicated tag once", () => {
    expect(tagCounts([{ tags: ["duda", "duda"] }]).duda).toBe(1);
  });

  it("reports zero to review for a fully tagged board", () => {
    expect(tagCounts([{ tags: ["titular"] }])[UNTAGGED]).toBe(0);
  });

  it("handles an empty board without inventing keys", () => {
    expect(tagCounts([])).toEqual({ [UNTAGGED]: 0 });
  });
});

describe("toggleTag", () => {
  it("adds one that is not selected and removes one that is", () => {
    expect(toggleTag([], "titular")).toEqual(["titular"]);
    expect(toggleTag(["titular", "duda"], "titular")).toEqual(["duda"]);
  });

  it("does not mutate the selection it was given", () => {
    const selected = ["titular"];
    toggleTag(selected, "duda");
    expect(selected).toEqual(["titular"]);
  });
});
