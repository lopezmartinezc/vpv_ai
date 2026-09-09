import type { DraftValuePlayer } from "@/types";

/**
 * A draft simulator that models how THIS league actually drafts, not how it
 * ought to. The point is not to produce an optimal draft — the board already
 * does that — but to answer "if I pick 5th, who is realistically still there
 * when my turn comes back?".
 *
 * The bot behaviour encodes what the admin has observed over many drafts:
 *
 *  - a big-team keeper always goes in the first round;
 *  - whoever takes a starting keeper takes his team-mate in the last rounds,
 *    to have that team's goal covered;
 *  - managers overvalue players from Madrid/Barça/Atlético, because a top-team
 *    starter feels safer to field every week;
 *  - everyone fills roughly the same 2/8/7/6 shape.
 *
 * Everything runs in the browser off the board that is already loaded. Nothing
 * is persisted.
 */

export const BIG_TEAMS = ["Real Madrid", "Barcelona", "Atlético", "Atletico"] as const;

/** Shape everybody drafts towards. It sums to 23 of the 26 squad places on
 * purpose: the last few picks go to whoever is best regardless of position,
 * which is what actually happens. So this is a SOFT target — passing it makes a
 * position unattractive, not forbidden. */
export const ROSTER_TARGET: Record<string, number> = {
  POR: 2,
  DEF: 8,
  MED: 7,
  DEL: 6,
};

/** Nobody drafts a fourth keeper. This one IS hard. */
export const MAX_KEEPERS = 3;

/** Score multiplier once a position has met its target. Low enough that a
 * needed position wins, high enough that a clearly better player still gets
 * taken. */
const OVER_TARGET_PENALTY = 0.3;

/** Rounds from the end in which a keeper owner goes looking for the backup even
 * if his raw value never made him attractive. */
const HANDCUFF_LAST_ROUNDS = 6;

/** Round-1 shove for an elite keeper. Enough to make him a first-round pick,
 * NOT enough to go first: the observed order is the top forwards and
 * midfielders of the big teams, with the big three's keepers following inside
 * the same round. At 1.8 a 250-point keeper scored 450 and outranked every
 * forward, so picks 1-3 were always keepers and the best forward survived to
 * the fourth slot — which is how "my first pick never changes" showed up. */
const ROUND1_KEEPER_SHOVE = 1.25;

/** How many keepers are "the ones that go in round one". Observed: the starters
 * of Madrid, Barça and Atlético — three, not one per manager. Shoving every
 * big-team keeper instead sent all eleven managers after a keeper in round 1
 * and left no understudies for the handcuff. */
const ELITE_KEEPERS = 3;

/** How many names a bot chooses between. Small early, wider later: in the first
 * rounds the board is obvious and everyone takes one of the same two or three
 * players, while by the middle rounds managers genuinely disagree. A flat width
 * made round 1 so noisy that the best player survived to the sixth pick, which
 * is not what happens. */
function shortlistFor(round: number): number {
  if (round <= 2) return 2;
  if (round <= 5) return 3;
  return 5;
}

/** Round-1 penalty for keepers who are NOT one of the big three's. Nobody
 * spends a first-round pick on the ninth-best keeper; without this the noise
 * put four keepers in round 1. */
const ROUND1_OTHER_KEEPER_PENALTY = 0.25;

export interface SimOptions {
  participants: number;
  /** My 1-based slot in the draft order. */
  myPosition: number;
  rounds: number;
  seed: number;
  /** 0 = bots follow the board; 0.4 = they clearly favour the big three. */
  bigTeamBias: number;
  myOrder: "priority" | "vorp";
  /** Ignore who currently owns whom and draft the whole pool. On by default:
   * this is a planning tool, and ownership left over from a rehearsal draft
   * would quietly remove the best players from the simulation. */
  ignoreDrafted?: boolean;
}

export interface SimPick {
  pickNumber: number;
  round: number;
  participantId: number;
  isMe: boolean;
  player: DraftValuePlayer;
}

export interface SimSquad {
  participantId: number;
  isMe: boolean;
  players: DraftValuePlayer[];
}

export interface SimResult {
  picks: SimPick[];
  squads: SimSquad[];
  myPicks: SimPick[];
  /** True when the board ran out of eligible players before the last round —
   * a real possibility at keeper, where the pool is genuinely shallow. */
  exhausted: boolean;
  /** Players the simulation could not consider, and why. Surfaced, never
   * silent: a star missing from the draft looks like a broken simulator when it
   * is really a gap in the board. */
  excluded: ExcludedPlayer[];
}

export type ExclusionReason = "ya-fichado" | "sin-prioridad" | "sin-posicion";

export interface ExcludedPlayer {
  player: DraftValuePlayer;
  reason: ExclusionReason;
}

/** Deterministic PRNG so a seed always replays the same draft. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function isBigTeam(team: string): boolean {
  return BIG_TEAMS.some((t) => team.includes(t));
}

/** Whose turn it is at `pickNumber`, snake order. Mirrors the backend's
 * `_get_participant_for_pick` so the simulation matches the real draft. */
function slotForPick(pickNumber: number, participants: number): number {
  const round = Math.floor((pickNumber - 1) / participants) + 1;
  const posInRound = (pickNumber - 1) % participants;
  return round % 2 === 0 ? participants - posInRound : posInRound + 1;
}

function countAt(squad: DraftValuePlayer[], position: string): number {
  return squad.filter((x) => x.position === position).length;
}

/** Hard eligibility. Only the keeper ceiling is absolute. */
function isEligible(squad: DraftValuePlayer[], position: string): boolean {
  if (ROSTER_TARGET[position] == null) return false;
  if (position === "POR") return countAt(squad, "POR") < MAX_KEEPERS;
  return true;
}

/** How much a position is still wanted: 1 while below target, then penalised. */
function positionAppetite(squad: DraftValuePlayer[], position: string): number {
  return countAt(squad, position) < ROSTER_TARGET[position] ? 1 : OVER_TARGET_PENALTY;
}

export function simulateDraft(
  players: DraftValuePlayer[],
  options: SimOptions,
): SimResult {
  const {
    participants,
    myPosition,
    rounds,
    seed,
    bigTeamBias,
    myOrder,
    ignoreDrafted = true,
  } = options;
  const rand = mulberry32(seed);

  // Every reason a player cannot take part is recorded. Nothing is dropped in
  // silence: a name missing from the simulated draft has to be explainable, or
  // it reads as a broken simulator when it is really a gap in the data.
  const excluded: ExcludedPlayer[] = [];
  const available: DraftValuePlayer[] = [];
  for (const x of players) {
    if (!ignoreDrafted && x.is_drafted) excluded.push({ player: x, reason: "ya-fichado" });
    else if (x.priority == null) excluded.push({ player: x, reason: "sin-prioridad" });
    else if (ROSTER_TARGET[x.position] == null)
      excluded.push({ player: x, reason: "sin-posicion" });
    else available.push(x);
  }
  // The specific keepers that go early: the best of the big three, by value.
  const eliteKeeperIds = new Set(
    available
      .filter((x) => x.position === "POR" && isBigTeam(x.team_name))
      .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))
      .slice(0, ELITE_KEEPERS)
      .map((x) => x.player_id),
  );
  const taken = new Set<number>();
  const squads = new Map<number, DraftValuePlayer[]>();
  for (let i = 1; i <= participants; i++) squads.set(i, []);

  const picks: SimPick[] = [];
  const totalPicks = participants * rounds;
  let exhausted = false;

  for (let pickNumber = 1; pickNumber <= totalPicks; pickNumber++) {
    const round = Math.floor((pickNumber - 1) / participants) + 1;
    const slot = slotForPick(pickNumber, participants);
    const squad = squads.get(slot)!;
    const isMe = slot === myPosition;

    const pool = available.filter(
      (x) => !taken.has(x.player_id) && isEligible(squad, x.position),
    );
    if (pool.length === 0) {
      exhausted = true;
      break;
    }

    const chosen = isMe
      ? pickForMe(pool, squad, myOrder)
      : pickForBot(pool, squad, round, rounds, bigTeamBias, eliteKeeperIds, rand);

    taken.add(chosen.player_id);
    squad.push(chosen);
    picks.push({ pickNumber, round, participantId: slot, isMe, player: chosen });
  }

  return {
    picks,
    squads: [...squads.entries()].map(([participantId, list]) => ({
      participantId,
      isMe: participantId === myPosition,
      players: list,
    })),
    myPicks: picks.filter((x) => x.isMe),
    exhausted,
    excluded,
  };
}

/** I follow the board, which is the whole point of having one — tempered only
 * by not stacking a position I have already filled. */
function pickForMe(
  pool: DraftValuePlayer[],
  squad: DraftValuePlayer[],
  order: "priority" | "vorp",
): DraftValuePlayer {
  return [...pool]
    .map((x) => ({
      player: x,
      score: ((x[order] ?? -1e9) as number) * positionAppetite(squad, x.position),
    }))
    .sort((a, b) => b.score - a.score)[0].player;
}

function pickForBot(
  pool: DraftValuePlayer[],
  squad: DraftValuePlayer[],
  round: number,
  rounds: number,
  bigTeamBias: number,
  eliteKeeperIds: ReadonlySet<number>,
  rand: () => number,
): DraftValuePlayer {
  const keepers = squad.filter((x) => x.position === "POR");
  const mate =
    keepers.length === 1
      ? pool.find((x) => x.position === "POR" && x.team_name === keepers[0].team_name)
      : undefined;

  // The handcuff is a deliberate plan, not a coincidence: once a manager holds
  // a keeper he saves the second slot for that keeper's understudy and takes
  // him late, when the pick costs nothing. So while the mate is still on the
  // board, no OTHER keeper is considered...
  const candidates = mate ? pool.filter((x) => x.position !== "POR" || x === mate) : pool;
  // ...and once the late rounds arrive, he is taken outright. Scoring him would
  // not work: a backup keeper's projection is tiny by construction.
  if (mate && round > rounds - HANDCUFF_LAST_ROUNDS) return mate;

  const scored = candidates.map((x) => {
    let score = (x.priority ?? 0) * positionAppetite(squad, x.position);
    if (isBigTeam(x.team_name)) score *= 1 + bigTeamBias;
    // First round: one of the big three's keepers is a status pick here — and
    // any other keeper is not a first-round pick at all.
    if (round === 1 && x.position === "POR") {
      score *= eliteKeeperIds.has(x.player_id)
        ? ROUND1_KEEPER_SHOVE
        : ROUND1_OTHER_KEEPER_PENALTY;
    }
    return { player: x, score };
  });

  scored.sort((a, b) => b.score - a.score);
  // Not always the top name: real managers disagree, and that disagreement is
  // what makes a simulated draft informative rather than a fixed list.
  const shortlist = scored.slice(0, shortlistFor(round));
  return shortlist[Math.floor(rand() * shortlist.length)].player;
}
