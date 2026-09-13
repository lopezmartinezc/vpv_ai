import Link from "next/link";
import { appliesToCompetition } from "@/lib/competition-scope";
import { withSeason } from "@/lib/season-link";
import { formatEuros } from "@/lib/weekly-payments";
import type { CopaFullResponse, EconomyResponse, GroupStandingsResponse } from "@/types";
import styles from "./home.module.css";

type Line = { label: string; value: string };

const RESULT: Record<number, string> = { 3: "V", 1: "E", 0: "D" };

/** Your place in the Copa and your result in the matchday followed; else the leader. */
export function copaLine(
  copa: CopaFullResponse | null,
  participantId: number | null,
  matchdayNumber: number | null,
): Line | null {
  const table = copa?.standings ?? [];
  if (!copa || table.length === 0) return null;
  const me = table.find((e) => e.participant_id === participantId);
  if (!me) return { label: "Copa", value: `lidera ${table[0].display_name}` };
  const result = copa.matchdays
    .find((md) => md.matchday_number === matchdayNumber)
    ?.results.find((r) => r.participant_id === participantId);
  const played = result
    ? ` · J${matchdayNumber}: ${RESULT[result.points] ?? "?"} ${result.goals_for}-${result.goals_against}`
    : "";
  return { label: "Copa", value: `${me.rank}.º de ${table.length}${played}` };
}

/**
 * Your weekly payments so far, counted as the Pagómetro counts them (what is
 * left of the balance without the fee and the draft). Yours only.
 */
export function weeklyLine(economy: EconomyResponse | null, participantId: number | null): Line | null {
  if (participantId === null) return null;
  const amounts = (economy?.balances ?? []).map((b) => ({
    id: b.participant_id,
    amount: b.net_balance - b.initial_fee - b.draft_fees,
  }));
  const mine = amounts.find((e) => e.id === participantId);
  if (!mine) return null;
  if (mine.amount === 0) return { label: "Semanales", value: "sin pagos todavía" };
  const place = 1 + amounts.filter((e) => e.amount > mine.amount).length;
  return {
    label: "Semanales",
    value: `has pagado ${formatEuros(mine.amount)} · ${place}.º que más ha pagado`,
  };
}

/** Your group in a tournament and its place; else the leading group. */
export function groupLine(
  groups: GroupStandingsResponse | null,
  participantId: number | null,
): Line | null {
  const list = groups?.groups ?? [];
  if (list.length === 0) return null;
  const mine = list.find((g) => g.members.some((m) => m.participant_id === participantId));
  if (!mine) {
    const leader = list.find((g) => g.rank === 1) ?? list[0];
    return { label: "Grupos", value: `lidera ${leader.group_name}` };
  }
  return { label: "Tu grupo", value: `${mine.group_name} · ${mine.rank}.º de ${list.length}` };
}

/**
 * The rest of the league, one line each with a link to its page: the full
 * tables live there, not on the home.
 */
export function LeagueSummary({
  seasonId,
  participantId,
  matchdayNumber,
  isTournament = false,
  economyEnabled = false,
  copa = null,
  economy = null,
  groups = null,
}: {
  seasonId: number;
  participantId: number | null;
  /** The matchday being followed, for your Copa result. */
  matchdayNumber: number | null;
  isTournament?: boolean;
  economyEnabled?: boolean;
  copa?: CopaFullResponse | null;
  economy?: EconomyResponse | null;
  groups?: GroupStandingsResponse | null;
}) {
  const rows: (Line & { href: string })[] = [];
  const copaRow = appliesToCompetition("/copa", isTournament)
    ? copaLine(copa, participantId, matchdayNumber)
    : null;
  if (copaRow) rows.push({ ...copaRow, href: "/copa" });
  const weeklyRow = economyEnabled ? weeklyLine(economy, participantId) : null;
  if (weeklyRow) rows.push({ ...weeklyRow, href: "/economia" });
  const groupRow = appliesToCompetition("/grupos", isTournament)
    ? groupLine(groups, participantId)
    : null;
  if (groupRow) rows.push({ ...groupRow, href: "/grupos" });
  if (rows.length === 0) return null;

  return (
    <section className={`${styles.card} ${styles.summary}`} aria-label="El resto de tu liga">
      <h2 className={styles.summaryTitle}>El resto de tu liga</h2>
      <ul className={styles.summaryList}>
        {rows.map((row) => (
          <li key={row.href}>
            <Link href={withSeason(row.href, seasonId)} className={styles.summaryRow}>
              <span className={styles.summaryLabel}>{row.label}</span>
              <span className={styles.summaryValue}>{row.value}</span>
              <span aria-hidden="true">→</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
