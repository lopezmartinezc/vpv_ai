-- =============================================================================
-- Liga VPV Fantasy -- PostgreSQL Schema
-- =============================================================================
-- File   : 00_create_schema.sql
-- Purpose: Creates all 18 tables for the VPV Fantasy league database.
--          Tables are dropped in reverse dependency order (leaf tables first)
--          to avoid FK constraint violations, then created in dependency order
--          (root tables first).
-- Source : modelo_datos_vpv.md
-- Date   : 2026-02-23
-- =============================================================================


-- =============================================================================
-- DROP TABLES (reverse dependency order -- leaf tables first)
-- =============================================================================

DROP TABLE IF EXISTS alembic_version               CASCADE;
DROP TABLE IF EXISTS invites                       CASCADE;
DROP TABLE IF EXISTS transactions                 CASCADE;
DROP TABLE IF EXISTS participant_matchday_scores  CASCADE;
DROP TABLE IF EXISTS lineup_players               CASCADE;
DROP TABLE IF EXISTS lineups                      CASCADE;
DROP TABLE IF EXISTS player_stats                 CASCADE;
DROP TABLE IF EXISTS matches                      CASCADE;
DROP TABLE IF EXISTS matchdays                    CASCADE;
DROP TABLE IF EXISTS draft_picks                  CASCADE;
DROP TABLE IF EXISTS drafts                       CASCADE;
DROP TABLE IF EXISTS players                      CASCADE;
DROP TABLE IF EXISTS competitions                 CASCADE;
DROP TABLE IF EXISTS teams                        CASCADE;
DROP TABLE IF EXISTS season_participants          CASCADE;
DROP TABLE IF EXISTS season_payments              CASCADE;
DROP TABLE IF EXISTS scoring_rules                CASCADE;
DROP TABLE IF EXISTS valid_formations             CASCADE;
DROP TABLE IF EXISTS seasons                      CASCADE;
DROP TABLE IF EXISTS users                        CASCADE;


-- =============================================================================
-- CREATE TABLES (dependency order -- root tables first)
-- =============================================================================

-- ----------------------------------------------------------------------------
-- 1. users -- Identidad unica de cada persona
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    email           VARCHAR(150),
    is_admin        BOOLEAN      NOT NULL DEFAULT FALSE,
    telegram_chat_id VARCHAR(50),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 2. seasons -- Configuracion de cada temporada
-- ----------------------------------------------------------------------------
CREATE TABLE seasons (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(15)  NOT NULL UNIQUE,  -- '2025-26'
    status              VARCHAR(20)  NOT NULL DEFAULT 'setup',
                        -- setup | draft | active | winter_draft | finished
    matchday_start      SMALLINT     NOT NULL,  -- Jornada inicio
    matchday_end        SMALLINT,               -- Jornada fin (puede ser NULL al crear)
    matchday_current    SMALLINT     NOT NULL DEFAULT 0,
    matchday_winter     SMALLINT,               -- Jornada del draft invierno
    matchday_scanned    SMALLINT     NOT NULL DEFAULT 0,
    draft_pool_size     SMALLINT     NOT NULL DEFAULT 26,  -- Jugadores por participante
    lineup_deadline_min SMALLINT     NOT NULL DEFAULT 30,  -- Minutos antes del 1er partido
    total_participants  SMALLINT     NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 3. valid_formations -- Formaciones permitidas
-- ----------------------------------------------------------------------------
CREATE TABLE valid_formations (
    id              SERIAL PRIMARY KEY,
    formation       VARCHAR(10) NOT NULL UNIQUE,
    defenders       SMALLINT    NOT NULL,
    midfielders     SMALLINT    NOT NULL,
    forwards        SMALLINT    NOT NULL
);

-- ----------------------------------------------------------------------------
-- 4. scoring_rules -- Reglas de puntuacion configurables por temporada
-- ----------------------------------------------------------------------------
CREATE TABLE scoring_rules (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    rule_key        VARCHAR(50)  NOT NULL,
    position        VARCHAR(3),  -- NULL = aplica a todas, 'POR','DEF','MED','DEL'
    value           DECIMAL(5,2) NOT NULL,
    description     VARCHAR(200),
    UNIQUE(season_id, rule_key, position)
);

-- ----------------------------------------------------------------------------
-- 5. season_payments -- Configuracion economica por temporada
-- ----------------------------------------------------------------------------
CREATE TABLE season_payments (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    payment_type    VARCHAR(30)  NOT NULL,
                    -- initial_fee | weekly_position | winter_draft_change | prize
    position_rank   SMALLINT,    -- Para weekly_position y prize: puesto (1,2,3...)
    amount          DECIMAL(8,2) NOT NULL,
    description     VARCHAR(200),
    UNIQUE(season_id, payment_type, position_rank)
);

-- ----------------------------------------------------------------------------
-- 6. season_participants -- Participantes de cada temporada
-- ----------------------------------------------------------------------------
CREATE TABLE season_participants (
    id              SERIAL PRIMARY KEY,
    season_id       INT      NOT NULL REFERENCES seasons(id),
    user_id         INT      NOT NULL REFERENCES users(id),
    draft_order     SMALLINT,  -- Puesto en el sorteo del draft (1,2,3...)
    is_active       BOOLEAN  NOT NULL DEFAULT TRUE,
    UNIQUE(season_id, user_id)
);

-- ----------------------------------------------------------------------------
-- 7. teams -- Equipos de La Liga por temporada
-- ----------------------------------------------------------------------------
CREATE TABLE teams (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    name            VARCHAR(100) NOT NULL,
    short_name      VARCHAR(10),
    slug            VARCHAR(100) NOT NULL,  -- nom_url del scraping
    logo_path       VARCHAR(255),
    UNIQUE(season_id, slug)
);

-- ----------------------------------------------------------------------------
-- 8. competitions -- Preparada para futuro (playoffs, copa)
-- ----------------------------------------------------------------------------
CREATE TABLE competitions (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    name            VARCHAR(100) NOT NULL,
    type            VARCHAR(20)  NOT NULL,  -- 'league' | 'playoff' | 'cup'
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
    config          JSONB,  -- Configuracion flexible (formato, rondas, etc.)
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 9. players -- Jugadores disponibles por temporada
-- ----------------------------------------------------------------------------
CREATE TABLE players (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    team_id         INT          NOT NULL REFERENCES teams(id),
    name            VARCHAR(200) NOT NULL,
    display_name    VARCHAR(200) NOT NULL,  -- nom_hum
    slug            VARCHAR(200) NOT NULL,  -- nom_url del scraping
    position        VARCHAR(3)   NOT NULL,  -- POR, DEF, MED, DEL
    photo_path      VARCHAR(255),
    source_url      VARCHAR(500),  -- URL original futbolfantasy
    is_available    BOOLEAN      NOT NULL DEFAULT TRUE,  -- Disponible para draft
    owner_id        INT          REFERENCES season_participants(id),  -- NULL = sin dueno
    UNIQUE(season_id, slug)
);

CREATE INDEX idx_players_season ON players(season_id);
CREATE INDEX idx_players_owner  ON players(owner_id);
CREATE INDEX idx_players_team   ON players(team_id);

-- ----------------------------------------------------------------------------
-- 10. drafts -- Eventos de draft
-- ----------------------------------------------------------------------------
CREATE TABLE drafts (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    draft_type      VARCHAR(20)  NOT NULL,  -- 'snake' | 'linear'
    phase           VARCHAR(20)  NOT NULL,  -- 'preseason' | 'winter'
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
                    -- pending | in_progress | completed
    current_round   SMALLINT     NOT NULL DEFAULT 0,
    current_pick    SMALLINT     NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 11. draft_picks -- Cada eleccion del draft
-- ----------------------------------------------------------------------------
CREATE TABLE draft_picks (
    id              SERIAL PRIMARY KEY,
    draft_id        INT      NOT NULL REFERENCES drafts(id),
    participant_id  INT      NOT NULL REFERENCES season_participants(id),
    player_id       INT      NOT NULL REFERENCES players(id),
    round_number    SMALLINT NOT NULL,
    pick_number     SMALLINT NOT NULL,  -- Orden global (1, 2, 3...)
    picked_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(draft_id, pick_number),
    UNIQUE(draft_id, player_id)
);

CREATE INDEX idx_draft_picks_participant ON draft_picks(participant_id);

-- ----------------------------------------------------------------------------
-- 12. matchdays -- Jornadas de La Liga
-- ----------------------------------------------------------------------------
CREATE TABLE matchdays (
    id              SERIAL PRIMARY KEY,
    season_id       INT      NOT NULL REFERENCES seasons(id),
    number          SMALLINT NOT NULL,   -- Numero de jornada (1-38)
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- pending | open | closed | scored | completed
    counts          BOOLEAN  NOT NULL DEFAULT TRUE,  -- Computa para la clasificacion?
    first_match_at  TIMESTAMPTZ,  -- Fecha/hora del primer partido (para deadline)
    deadline_at     TIMESTAMPTZ,  -- Calculado: first_match_at - deadline_min
    stats_ok        BOOLEAN  NOT NULL DEFAULT FALSE,
    UNIQUE(season_id, number)
);

-- ----------------------------------------------------------------------------
-- 13. matches -- Partidos de La Liga
-- ----------------------------------------------------------------------------
CREATE TABLE matches (
    id              SERIAL PRIMARY KEY,
    matchday_id     INT          NOT NULL REFERENCES matchdays(id),
    home_team_id    INT          NOT NULL REFERENCES teams(id),
    away_team_id    INT          NOT NULL REFERENCES teams(id),
    home_score      SMALLINT,
    away_score      SMALLINT,
    result          VARCHAR(100),  -- Texto del resultado (ej: "2 - 1")
    counts          BOOLEAN      NOT NULL DEFAULT TRUE,  -- Partido individual computa
    stats_ok        BOOLEAN      NOT NULL DEFAULT FALSE,
    source_id       INT,          -- id_part del scraping
    source_url      VARCHAR(200), -- url_part del scraping
    stats_crc       VARCHAR(20),  -- CRC for change detection (scraping)
    played_at       TIMESTAMPTZ,
    UNIQUE(matchday_id, home_team_id, away_team_id)
);

-- ----------------------------------------------------------------------------
-- 14. player_stats -- Estadisticas de jugador por jornada
--                     (datos del scraping + puntos calculados)
-- ----------------------------------------------------------------------------
CREATE TABLE player_stats (
    id                  SERIAL PRIMARY KEY,
    player_id           INT      NOT NULL REFERENCES players(id),
    matchday_id         INT      NOT NULL REFERENCES matchdays(id),
    match_id            INT      REFERENCES matches(id),

    -- Estado
    processed           BOOLEAN  NOT NULL DEFAULT FALSE,

    -- Posicion en esta jornada (puede diferir de players.position si hubo cambio en draft invierno)
    position            VARCHAR(3) NOT NULL,  -- POR | DEF | MED | DEL

    -- Participacion
    played              BOOLEAN  NOT NULL DEFAULT FALSE,
    event               VARCHAR(60),   -- 'Entrada' | 'Salida' | NULL
    event_minute        SMALLINT,
    minutes_played      SMALLINT,

    -- Resultado del equipo (desde perspectiva del jugador)
    home_score          SMALLINT,      -- res_l
    away_score          SMALLINT,      -- res_v
    result              SMALLINT,      -- 0=derrota, 1=empate, 2=victoria
    goals_for           SMALLINT,      -- gol_f
    goals_against       SMALLINT,      -- gol_c

    -- Datos crudos del scraping (conteos)
    goals               SMALLINT DEFAULT 0,
    penalty_goals       SMALLINT DEFAULT 0,
    penalties_missed    SMALLINT DEFAULT 0,
    own_goals           SMALLINT DEFAULT 0,
    assists             SMALLINT DEFAULT 0,
    penalties_saved     SMALLINT DEFAULT 0,
    yellow_card         BOOLEAN  DEFAULT FALSE,
    yellow_removed      BOOLEAN  DEFAULT FALSE,  -- Amarilla quitada por comite
    double_yellow       BOOLEAN  DEFAULT FALSE,
    red_card            BOOLEAN  DEFAULT FALSE,
    woodwork            SMALLINT DEFAULT 0,       -- tiro_palo
    penalties_won       SMALLINT DEFAULT 0,       -- pen_for
    penalties_committed SMALLINT DEFAULT 0,       -- pen_com

    -- Valoracion mediatica (datos crudos)
    marca_rating        VARCHAR(10),   -- est_marca: "1","2","3","4","-","SC"
    as_picas            VARCHAR(10),   -- picas_as: "0","1","2","3","-","SC"

    -- PUNTOS CALCULADOS (usando scoring_rules de la temporada)
    pts_play            SMALLINT DEFAULT 0,
    pts_starter         SMALLINT DEFAULT 0,
    pts_result          SMALLINT DEFAULT 0,
    pts_clean_sheet     SMALLINT DEFAULT 0,
    pts_goals           SMALLINT DEFAULT 0,
    pts_penalty_goals   SMALLINT DEFAULT 0,
    pts_assists         SMALLINT DEFAULT 0,
    pts_penalties_saved SMALLINT DEFAULT 0,
    pts_woodwork        SMALLINT DEFAULT 0,
    pts_penalties_won   SMALLINT DEFAULT 0,
    pts_penalties_missed SMALLINT DEFAULT 0,  -- negativo
    pts_own_goals       SMALLINT DEFAULT 0,   -- negativo
    pts_yellow          SMALLINT DEFAULT 0,   -- negativo
    pts_red             SMALLINT DEFAULT 0,   -- negativo
    pts_pen_committed   SMALLINT DEFAULT 0,   -- negativo
    pts_marca           SMALLINT DEFAULT 0,
    pts_as              SMALLINT DEFAULT 0,
    pts_marca_as        SMALLINT DEFAULT 0,   -- suma marca + as
    pts_total           SMALLINT DEFAULT 0,   -- ptos_jor

    UNIQUE(player_id, matchday_id)
);

CREATE INDEX idx_player_stats_matchday ON player_stats(matchday_id);
CREATE INDEX idx_player_stats_player   ON player_stats(player_id);

-- ----------------------------------------------------------------------------
-- 15. lineups -- Alineacion de cada participante por jornada
-- ----------------------------------------------------------------------------
CREATE TABLE lineups (
    id              SERIAL PRIMARY KEY,
    participant_id  INT          NOT NULL REFERENCES season_participants(id),
    matchday_id     INT          NOT NULL REFERENCES matchdays(id),
    formation       VARCHAR(10)  NOT NULL,  -- '1-4-3-3', '1-3-5-2', etc.
    confirmed       BOOLEAN      NOT NULL DEFAULT FALSE,
    confirmed_at    TIMESTAMPTZ,
    telegram_sent   BOOLEAN      NOT NULL DEFAULT FALSE,
    telegram_sent_at TIMESTAMPTZ,
    image_path      VARCHAR(255),  -- Ruta de la imagen generada
    total_points    SMALLINT     DEFAULT 0,  -- Suma de puntos del 11 (calculado)
    UNIQUE(participant_id, matchday_id)
);

-- ----------------------------------------------------------------------------
-- 16. lineup_players -- Los 11 jugadores alineados
-- ----------------------------------------------------------------------------
CREATE TABLE lineup_players (
    id              SERIAL PRIMARY KEY,
    lineup_id       INT      NOT NULL REFERENCES lineups(id) ON DELETE CASCADE,
    player_id       INT      NOT NULL REFERENCES players(id),
    position_slot   VARCHAR(3) NOT NULL,  -- POR, DEF, MED, DEL (posicion en la formacion)
    display_order   SMALLINT NOT NULL,    -- Orden de visualizacion (1-11)
    points          SMALLINT DEFAULT 0,   -- Puntos de este jugador en esta jornada
    UNIQUE(lineup_id, player_id),
    UNIQUE(lineup_id, display_order)
);

-- ----------------------------------------------------------------------------
-- 17. participant_matchday_scores -- Puntuacion de cada participante por jornada
-- ----------------------------------------------------------------------------
CREATE TABLE participant_matchday_scores (
    id              SERIAL PRIMARY KEY,
    participant_id  INT      NOT NULL REFERENCES season_participants(id),
    matchday_id     INT      NOT NULL REFERENCES matchdays(id),
    total_points    SMALLINT NOT NULL DEFAULT 0,
    ranking         SMALLINT,  -- Puesto en esa jornada (para calculo de pago semanal)
    UNIQUE(participant_id, matchday_id)
);

-- ----------------------------------------------------------------------------
-- 18. transactions -- Movimientos economicos
-- ----------------------------------------------------------------------------
CREATE TABLE transactions (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    participant_id  INT          NOT NULL REFERENCES season_participants(id),
    matchday_id     INT          REFERENCES matchdays(id),  -- NULL para cuota inicial/premios
    type            VARCHAR(30)  NOT NULL,
                    -- initial_fee | weekly_payment | winter_draft_fee | prize | adjustment
    amount          DECIMAL(8,2) NOT NULL,  -- Positivo = debe pagar, Negativo = recibe
    description     VARCHAR(200),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transactions_participant ON transactions(participant_id);
CREATE INDEX idx_transactions_season      ON transactions(season_id);

-- ----------------------------------------------------------------------------
-- 19. invites -- Invitaciones de registro
-- ----------------------------------------------------------------------------
CREATE TABLE invites (
    id              SERIAL PRIMARY KEY,
    token           VARCHAR(255) NOT NULL,
    target_user_id  INT          REFERENCES users(id),
    created_by_id   INT          NOT NULL REFERENCES users(id),
    used_by_id      INT          REFERENCES users(id),
    expires_at      TIMESTAMPTZ  NOT NULL,
    used_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX ix_invites_token ON invites(token);

-- ----------------------------------------------------------------------------
-- 20. player_ownership_log -- Historico de propiedad de jugadores
-- ----------------------------------------------------------------------------
CREATE TABLE player_ownership_log (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    player_id       INT          NOT NULL REFERENCES players(id),
    participant_id  INT          REFERENCES season_participants(id),
    from_matchday   SMALLINT     NOT NULL,
    CONSTRAINT uq_ownership_log_player_matchday
        UNIQUE (season_id, player_id, from_matchday)
);

CREATE INDEX idx_ownership_log_season      ON player_ownership_log(season_id);
CREATE INDEX idx_ownership_log_participant ON player_ownership_log(participant_id);
CREATE INDEX idx_ownership_log_player      ON player_ownership_log(player_id);

-- ----------------------------------------------------------------------------
-- Alembic version tracking
-- ----------------------------------------------------------------------------
CREATE TABLE alembic_version (
    version_num     VARCHAR(32)  NOT NULL PRIMARY KEY
);
