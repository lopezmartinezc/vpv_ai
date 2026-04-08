"""Reverse sync: push matchday data from PostgreSQL back to legacy MySQL.

The old site (ligavpv.com) reads from MySQL jornadas_temp.  This service
writes lineups + player_stats back so both sites stay in sync during the
migration period.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ReverseSyncResult:
    matchday_number: int
    season_name: str
    stats_upserted: int
    lineups_upserted: int
    errors: list[str]


class MysqlSyncService:
    def __init__(self, pg_session: AsyncSession) -> None:
        self.pg = pg_session

    def _get_mysql_conn(self) -> Any:
        """Create a synchronous MySQL connection (short-lived)."""
        import mysql.connector

        if not settings.mysql_host:
            raise RuntimeError("MySQL no configurado (MYSQL_HOST vacio)")
        return mysql.connector.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset="utf8mb4",
        )

    async def reverse_sync_matchday(
        self, season_id: int, matchday_number: int
    ) -> ReverseSyncResult:
        """Push PG data for one matchday back to MySQL jornadas_temp."""
        errors: list[str] = []

        # 1. Get season name + matchday_id from PG
        row = await self.pg.execute(
            text(
                "SELECT s.name, md.id FROM seasons s "
                "JOIN matchdays md ON md.season_id = s.id "
                "WHERE s.id = :sid AND md.number = :num"
            ),
            {"sid": season_id, "num": matchday_number},
        )
        info = row.one_or_none()
        if info is None:
            raise ValueError(f"Season {season_id} / J{matchday_number} not found")
        season_name, matchday_id = info.name, info.id

        # 2. Get slot_map: participant_id → MySQL id_user (slot number)
        # In the old system, id_user is the participant's "slot" number.
        # We store this in season_participants.draft_order as a rough equivalent,
        # but the real mapping is the participant's position in the season.
        # The migration used usuarios_temp.id as slot. We need the reverse.
        slot_rows = await self.pg.execute(
            text(
                "SELECT sp.id as participant_id, sp.user_id, u.username "
                "FROM season_participants sp "
                "JOIN users u ON sp.user_id = u.id "
                "WHERE sp.season_id = :sid AND sp.is_active = TRUE "
                "ORDER BY sp.id"
            ),
            {"sid": season_id},
        )
        participants = slot_rows.all()

        # 3. Get player_stats for this matchday (ALL players, not just lineup)
        stats_rows = await self.pg.execute(
            text("""
                SELECT p.slug, ps.position, p.display_name,
                       t.name as team_name, p.owner_id,
                       ps.processed, ps.played, ps.event, ps.event_minute,
                       ps.minutes_played, ps.home_score, ps.away_score,
                       ps.result, ps.goals_for, ps.goals_against,
                       ps.goals, ps.penalty_goals, ps.penalties_missed,
                       ps.own_goals, ps.assists, ps.penalties_saved,
                       ps.yellow_card, ps.yellow_removed, ps.double_yellow,
                       ps.red_card, ps.woodwork, ps.penalties_won,
                       ps.penalties_committed, ps.marca_rating, ps.as_picas,
                       ps.pts_marca, ps.pts_as, ps.pts_marca_as,
                       ps.pts_total, ps.pts_play, ps.pts_starter,
                       ps.pts_result, ps.pts_clean_sheet, ps.pts_goals,
                       ps.pts_penalty_goals, ps.pts_penalties_missed,
                       ps.pts_own_goals, ps.pts_assists, ps.pts_penalties_saved,
                       ps.pts_yellow, ps.pts_red, ps.pts_woodwork,
                       ps.pts_penalties_won, ps.pts_pen_committed
                FROM player_stats ps
                JOIN players p ON ps.player_id = p.id
                JOIN teams t ON p.team_id = t.id
                WHERE ps.matchday_id = :md_id
                ORDER BY p.slug
            """),
            {"md_id": matchday_id},
        )
        stats = stats_rows.all()

        # 4. Get lineup data (who is alineado + order)
        lineup_rows = await self.pg.execute(
            text("""
                SELECT l.participant_id, lp.player_id, p.slug,
                       lp.position_slot, lp.display_order
                FROM lineups l
                JOIN lineup_players lp ON lp.lineup_id = l.id
                JOIN players p ON lp.player_id = p.id
                WHERE l.matchday_id = :md_id
            """),
            {"md_id": matchday_id},
        )
        lineup_data = lineup_rows.all()

        # Build lookup: slug → (participant_id, display_order)
        lineup_map: dict[str, tuple[int, int]] = {}
        for lr in lineup_data:
            lineup_map[lr.slug] = (lr.participant_id, lr.display_order)

        # Build participant_id → slot (MySQL id_user)
        # Get the mapping from MySQL directly
        mysql_conn = self._get_mysql_conn()
        try:
            cursor = mysql_conn.cursor(dictionary=True)

            # Get slot mapping from MySQL usuarios_temp
            cursor.execute(
                "SELECT id, nombre FROM usuarios_temp WHERE temporada = %s",
                (season_name,),
            )
            mysql_slots = cursor.fetchall()
            # Map by username match
            username_to_slot: dict[str, int] = {}
            for ms in mysql_slots:
                username_to_slot[ms["nombre"].strip().lower()] = ms["id"]

            # Map participant_id → mysql slot
            part_to_slot: dict[int, int] = {}
            for p in participants:
                # Try matching by username
                slot = username_to_slot.get(p.username.strip().lower())
                if slot is not None:
                    part_to_slot[p.participant_id] = slot

            # 5. UPSERT player_stats into jornadas_temp
            stats_count = 0
            for s in stats:
                # Determine alineado and id_user
                lu = lineup_map.get(s.slug)
                alineado = 1 if lu else 0
                id_user = part_to_slot.get(lu[0], 0) if lu else 0
                order_ast = lu[1] if lu else 0

                try:
                    cursor.execute(
                        """
                        INSERT INTO jornadas_temp (
                            nom_url, jornada, temporada, equipo, pos, nom_hum,
                            id_user, order_astudillo, alineado, estadistica,
                            play, res_l, res_v, res, gol_f, gol_c,
                            evento, min_evento, tiempo_jug,
                            gol, gol_p, pen_fall, gol_pp, asis, pen_par,
                            ama, ama_remove, ama_doble, roja,
                            tiro_palo, pen_for, pen_com,
                            est_marca, ptos_marca, picas_as, ptos_as, marca_as,
                            ptos_jor, ptos_jugar, ptos_titular, ptos_resultado,
                            ptos_imbatibilidad, ptos_gol, ptos_gol_p,
                            ptos_pen_fall, ptos_gol_pp, ptos_asis, ptos_pen_par,
                            ptos_ama, ptos_roja, ptos_tiro_palo,
                            ptos_pen_for, ptos_pen_com
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s
                        )
                        ON DUPLICATE KEY UPDATE
                            equipo=VALUES(equipo), pos=VALUES(pos), nom_hum=VALUES(nom_hum),
                            id_user=VALUES(id_user), order_astudillo=VALUES(order_astudillo),
                            alineado=VALUES(alineado), estadistica=VALUES(estadistica),
                            play=VALUES(play), res_l=VALUES(res_l), res_v=VALUES(res_v),
                            res=VALUES(res), gol_f=VALUES(gol_f), gol_c=VALUES(gol_c),
                            evento=VALUES(evento), min_evento=VALUES(min_evento),
                            tiempo_jug=VALUES(tiempo_jug),
                            gol=VALUES(gol), gol_p=VALUES(gol_p), pen_fall=VALUES(pen_fall),
                            gol_pp=VALUES(gol_pp), asis=VALUES(asis), pen_par=VALUES(pen_par),
                            ama=VALUES(ama), ama_remove=VALUES(ama_remove),
                            ama_doble=VALUES(ama_doble), roja=VALUES(roja),
                            tiro_palo=VALUES(tiro_palo), pen_for=VALUES(pen_for),
                            pen_com=VALUES(pen_com),
                            est_marca=VALUES(est_marca), ptos_marca=VALUES(ptos_marca),
                            picas_as=VALUES(picas_as), ptos_as=VALUES(ptos_as),
                            marca_as=VALUES(marca_as),
                            ptos_jor=VALUES(ptos_jor), ptos_jugar=VALUES(ptos_jugar),
                            ptos_titular=VALUES(ptos_titular),
                            ptos_resultado=VALUES(ptos_resultado),
                            ptos_imbatibilidad=VALUES(ptos_imbatibilidad),
                            ptos_gol=VALUES(ptos_gol), ptos_gol_p=VALUES(ptos_gol_p),
                            ptos_pen_fall=VALUES(ptos_pen_fall),
                            ptos_gol_pp=VALUES(ptos_gol_pp),
                            ptos_asis=VALUES(ptos_asis), ptos_pen_par=VALUES(ptos_pen_par),
                            ptos_ama=VALUES(ptos_ama), ptos_roja=VALUES(ptos_roja),
                            ptos_tiro_palo=VALUES(ptos_tiro_palo),
                            ptos_pen_for=VALUES(ptos_pen_for),
                            ptos_pen_com=VALUES(ptos_pen_com)
                        """,
                        (
                            s.slug,
                            matchday_number,
                            season_name,
                            s.team_name,
                            s.position,
                            s.display_name,
                            id_user,
                            order_ast,
                            alineado,
                            int(s.processed or False),
                            int(s.played or False),
                            s.home_score,
                            s.away_score,
                            s.result,
                            s.goals_for,
                            s.goals_against,
                            s.event,
                            s.event_minute,
                            s.minutes_played,
                            s.goals,
                            s.penalty_goals,
                            s.penalties_missed,
                            s.own_goals,
                            s.assists,
                            s.penalties_saved,
                            int(s.yellow_card or False),
                            int(s.yellow_removed or False),
                            int(s.double_yellow or False),
                            int(s.red_card or False),
                            s.woodwork,
                            s.penalties_won,
                            s.penalties_committed,
                            s.marca_rating,
                            str(s.pts_marca) if s.pts_marca is not None else None,
                            s.as_picas,
                            str(s.pts_as) if s.pts_as is not None else None,
                            s.pts_marca_as,
                            s.pts_total,
                            s.pts_play,
                            s.pts_starter,
                            s.pts_result,
                            s.pts_clean_sheet,
                            s.pts_goals,
                            s.pts_penalty_goals,
                            s.pts_penalties_missed,
                            s.pts_own_goals,
                            s.pts_assists,
                            s.pts_penalties_saved,
                            s.pts_yellow,
                            s.pts_red,
                            s.pts_woodwork,
                            s.pts_penalties_won,
                            s.pts_pen_committed,
                        ),
                    )
                    stats_count += 1
                except Exception as exc:
                    errors.append(f"{s.slug}: {exc}")

            mysql_conn.commit()

            logger.info(
                "reverse_sync J%d: %d stats upserted, %d lineup entries, %d errors",
                matchday_number,
                stats_count,
                len(lineup_data),
                len(errors),
            )

        finally:
            cursor.close()
            mysql_conn.close()

        return ReverseSyncResult(
            matchday_number=matchday_number,
            season_name=season_name,
            stats_upserted=stats_count,
            lineups_upserted=len(lineup_data),
            errors=errors,
        )
