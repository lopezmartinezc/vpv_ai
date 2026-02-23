# Modelo de Datos - Liga VPV Fantasy (PostgreSQL)

## 📐 Diagrama de Relaciones

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   seasons    │────<│ season_payments   │     │      users       │
│             │     └──────────────────┘     │   (identidad)    │
│             │                              └────────┬─────────┘
│             │     ┌──────────────────┐              │
│             │────<│  scoring_rules   │     ┌────────┴─────────┐
│             │     └──────────────────┘     │   season_        │
│             │                              │   participants   │
│             │──────────────────────────────<│  (por temporada) │
│             │                              └────────┬─────────┘
│             │                                       │
│             │     ┌──────────────────┐              │
│             │────<│     teams        │              │
└──────┬──────┘     └───────┬──────────┘              │
       │                    │                         │
       │            ┌───────┴──────────┐              │
       │            │    players       │              │
       │            │  (por temporada) │              │
       │            └───────┬──────────┘              │
       │                    │                         │
       │            ┌───────┴──────────┐     ┌────────┴─────────┐
       │            │  player_stats    │     │   draft_picks    │
       │            │ (jugador×jornada)│     │  (elecciones)    │
       │            └───────┬──────────┘     └──────────────────┘
       │                    │                         │
       │            ┌───────┴──────────┐              │
       │            │    matches       │     ┌────────┴─────────┐
       │            │   (partidos)     │     │    drafts        │
       │            └──────────────────┘     └──────────────────┘
       │                                              
       │            ┌──────────────────┐     ┌──────────────────┐
       └───────────<│  matchdays       │────<│   lineups        │
                    │  (jornadas)      │     │  (alineaciones)  │
                    └──────────────────┘     └───────┬──────────┘
                                                     │
                                             ┌───────┴──────────┐
                                             │  lineup_players  │
                                             │  (11 titulares)  │
                                             └──────────────────┘
                                             
                    ┌──────────────────┐
                    │ participant_     │
                    │ matchday_scores  │
                    │ (puntos jornada) │
                    └──────────────────┘
                    
                    ┌──────────────────┐
                    │   transactions   │
                    │  (movimientos €) │
                    └──────────────────┘
                    
                    ┌──────────────────┐
                    │  competitions    │
                    │  (futuro: copa,  │
                    │   playoffs)      │
                    └──────────────────┘
```

---

## 📋 Tablas

### 1. `users` — Identidad única de cada persona

```sql
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
```

**Diferencia con MySQL actual**: `usuarios_temp` duplicaba el usuario por temporada. Ahora el usuario es único y se vincula a temporadas mediante `season_participants`.

---

### 2. `seasons` — Configuración de cada temporada

```sql
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
```

**Diferencia con MySQL**: `temporadas` solo tenía jornada_inicial, jornada_actual, jornada_cambios, total_user, jornada_escaneada. Ahora se añade estado de la temporada, deadline configurable y draft_pool_size.

---

### 3. `scoring_rules` — Reglas de puntuación configurables por temporada

```sql
CREATE TABLE scoring_rules (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    rule_key        VARCHAR(50)  NOT NULL,
    position        VARCHAR(3),  -- NULL = aplica a todas, 'POR','DEF','MED','DEL'
    value           DECIMAL(5,2) NOT NULL,
    description     VARCHAR(200),
    UNIQUE(season_id, rule_key, position)
);
```

**Datos de ejemplo** (una temporada):

| rule_key | position | value | description |
|----------|----------|-------|-------------|
| `ptos_jugar` | NULL | 1 | Jugar el partido |
| `ptos_titular` | NULL | 1 | Ser titular |
| `ptos_resultado_win` | NULL | 2 | Victoria del equipo |
| `ptos_resultado_draw` | NULL | 1 | Empate del equipo |
| `ptos_resultado_loss` | NULL | 0 | Derrota del equipo |
| `ptos_gol` | POR | 10 | Gol de portero |
| `ptos_gol` | DEF | 8 | Gol de defensa |
| `ptos_gol` | MED | 7 | Gol de mediocampista |
| `ptos_gol` | DEL | 5 | Gol de delantero |
| `ptos_imbatibilidad_clean` | POR | 4 | Portería a 0 (POR) |
| `ptos_imbatibilidad_clean` | DEF | 3 | Portería a 0 (DEF) |
| `ptos_imbatibilidad_min` | POR | 65 | Minutos mínimos imbatibilidad POR |
| `ptos_imbatibilidad_min` | DEF | 45 | Minutos mínimos imbatibilidad DEF |
| `ptos_imbatibilidad_1gol` | POR | 0 | POR con 1 gol encajado |
| `ptos_imbatibilidad_per_gol` | POR | -1 | POR penalización por gol (>1 gol) |
| `ptos_gol_p` | NULL | 5 | Gol de penalti |
| `ptos_asis` | NULL | 2 | Asistencia |
| `ptos_pen_par` | NULL | 5 | Penalti parado |
| `ptos_tiro_palo` | NULL | 1 | Tiro al palo |
| `ptos_pen_for` | NULL | 1 | Penalti forzado |
| `ptos_pen_fall` | NULL | -3 | Penalti fallado |
| `ptos_gol_pp` | NULL | -2 | Gol en propia puerta |
| `ptos_ama` | NULL | -1 | Tarjeta amarilla |
| `ptos_roja` | NULL | -3 | Roja directa o doble amarilla |
| `ptos_pen_com` | NULL | -1 | Penalti cometido |
| `ptos_marca_1` | NULL | 1 | Marca 1 estrella |
| `ptos_marca_2` | NULL | 2 | Marca 2 estrellas |
| `ptos_marca_3` | NULL | 3 | Marca 3 estrellas |
| `ptos_marca_4` | NULL | 4 | Marca 4 estrellas |
| `ptos_marca_no_jugo` | NULL | -1 | Marca "-" |
| `ptos_marca_sc` | NULL | 0 | Marca "SC" |
| `ptos_as_per_pica` | NULL | 1 | AS por cada pica |
| `ptos_as_no_jugo` | NULL | -1 | AS "-" |
| `ptos_as_sc` | NULL | 0 | AS "SC" |

**Ventaja**: Si la próxima temporada queréis que un gol de delantero valga 6 en vez de 5, se cambia aquí sin tocar código. Para copiar de una temporada a otra se hace un INSERT...SELECT.

---

### 4. `season_payments` — Configuración económica por temporada

```sql
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
```

**Ejemplo**:

| payment_type | position_rank | amount | description |
|---|---|---|---|
| `initial_fee` | NULL | 50.00 | Cuota inicial |
| `weekly_position` | 1 | 0.00 | 1º no paga |
| `weekly_position` | 2 | 0.00 | 2º no paga |
| `weekly_position` | 7 | 3.00 | 7º paga 3€ |
| `weekly_position` | 8 | 5.00 | 8º (último) paga 5€ |
| `winter_draft_change` | NULL | 2.00 | 2€ por cada cambio |
| `prize` | 1 | 200.00 | Premio al 1º |
| `prize` | 2 | 100.00 | Premio al 2º |
| `prize` | 3 | 50.00 | Premio al 3º |

---

### 5. `season_participants` — Participantes de cada temporada

```sql
CREATE TABLE season_participants (
    id              SERIAL PRIMARY KEY,
    season_id       INT      NOT NULL REFERENCES seasons(id),
    user_id         INT      NOT NULL REFERENCES users(id),
    draft_order     SMALLINT,  -- Puesto en el sorteo del draft (1,2,3...)
    is_active       BOOLEAN  NOT NULL DEFAULT TRUE,
    UNIQUE(season_id, user_id)
);
```

---

### 6. `teams` — Equipos de La Liga por temporada

```sql
CREATE TABLE teams (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    name            VARCHAR(100) NOT NULL,
    short_name      VARCHAR(10),
    slug            VARCHAR(100) NOT NULL,  -- nom_url del scraping
    logo_path       VARCHAR(255),
    UNIQUE(season_id, slug)
);
```

**Diferencia con MySQL**: `equipos` no tenía relación con temporada. Ahora soporta ascensos/descensos.

---

### 7. `players` — Jugadores disponibles por temporada

```sql
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
    owner_id        INT          REFERENCES season_participants(id),  -- NULL = sin dueño
    UNIQUE(season_id, slug)
);

CREATE INDEX idx_players_season ON players(season_id);
CREATE INDEX idx_players_owner ON players(owner_id);
CREATE INDEX idx_players_team ON players(team_id);
```

**Diferencia con MySQL**: No existía tabla de jugadores independiente. Estaba embebido en `jornadas_temp` y `alineaciones_temp` con nom_url repetido. Ahora el jugador tiene ID propio, equipo por FK, y owner para saber quién lo tiene.

**Importante — campos "estado actual"**:
- `team_id` = equipo **actual** del jugador. Un jugador puede cambiar de equipo en cualquier momento de la temporada (traspaso de mercado). El equipo real en cada jornada se obtiene desde `player_stats.match_id → matches`.
- `position` = posición **actual** del jugador. Puede cambiar durante el draft de invierno. La posición real en cada jornada está en `player_stats.position` y es la fuente de verdad para calcular puntos. El scraping actualiza ambos campos al cargar cada jornada.

---

### 8. `drafts` — Eventos de draft

```sql
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
```

---

### 9. `draft_picks` — Cada elección del draft

```sql
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
```

**Diferencia con MySQL**: No existía. El draft se gestionaba fuera de la app.

---

### 10. `matchdays` — Jornadas de La Liga

```sql
CREATE TABLE matchdays (
    id              SERIAL PRIMARY KEY,
    season_id       INT      NOT NULL REFERENCES seasons(id),
    number          SMALLINT NOT NULL,   -- Número de jornada (1-38)
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- pending | open | closed | scored | completed
    counts          BOOLEAN  NOT NULL DEFAULT TRUE,  -- ¿Computa para la clasificación?
    first_match_at  TIMESTAMPTZ,  -- Fecha/hora del primer partido (para deadline)
    deadline_at     TIMESTAMPTZ,  -- Calculado: first_match_at - deadline_min
    stats_ok        BOOLEAN  NOT NULL DEFAULT FALSE,
    UNIQUE(season_id, number)
);
```

**Diferencia con MySQL**: `list_jornadas_temp` mezclaba jornada con partido. Ahora están separados.

---

### 11. `matches` — Partidos de La Liga

```sql
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
    played_at       TIMESTAMPTZ,
    UNIQUE(matchday_id, home_team_id, away_team_id)
);
```

---

### 12. `player_stats` — Estadísticas de jugador por jornada (datos del scraping + puntos calculados)

```sql
CREATE TABLE player_stats (
    id                  SERIAL PRIMARY KEY,
    player_id           INT      NOT NULL REFERENCES players(id),
    matchday_id         INT      NOT NULL REFERENCES matchdays(id),
    match_id            INT      REFERENCES matches(id),
    
    -- Estado
    processed           BOOLEAN  NOT NULL DEFAULT FALSE,

    -- Posición en esta jornada (puede diferir de players.position si hubo cambio en draft invierno)
    position            VARCHAR(3) NOT NULL,  -- POR | DEF | MED | DEL

    -- Participación
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
    yellow_removed      BOOLEAN  DEFAULT FALSE,  -- Amarilla quitada por comité
    double_yellow       BOOLEAN  DEFAULT FALSE,
    red_card            BOOLEAN  DEFAULT FALSE,
    woodwork            SMALLINT DEFAULT 0,       -- tiro_palo
    penalties_won       SMALLINT DEFAULT 0,       -- pen_for
    penalties_committed SMALLINT DEFAULT 0,       -- pen_com
    
    -- Valoración mediática (datos crudos)
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
CREATE INDEX idx_player_stats_player ON player_stats(player_id);
```

**Diferencia con MySQL**: `jornadas_temp` mezclaba todo en una mega-tabla (datos del jugador, del partido, alineación fantasy, stats y puntos). Ahora está separado: el jugador real tiene sus stats aquí, la alineación fantasy va en `lineups`.

**Mapeo con MySQL actual**:

| MySQL `jornadas_temp` | PostgreSQL `player_stats` |
|---|---|
| `nom_url` + `jornada` + `temporada` | `player_id` + `matchday_id` |
| `pos` | `position` (fuente de verdad para puntos) |
| `play` | `played` |
| `evento` / `min_evento` | `event` / `event_minute` |
| `tiempo_jug` | `minutes_played` |
| `res_l` / `res_v` / `res` | `home_score` / `away_score` / `result` |
| `gol_f` / `gol_c` | `goals_for` / `goals_against` |
| `gol` / `gol_p` / `pen_fall` / ... | `goals` / `penalty_goals` / `penalties_missed` / ... |
| `est_marca` / `picas_as` | `marca_rating` / `as_picas` |
| `ptos_jugar` / `ptos_titular` / ... | `pts_play` / `pts_starter` / ... |
| `ptos_jor` | `pts_total` |

---

### 13. `lineups` — Alineación de cada participante por jornada

```sql
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
```

---

### 14. `lineup_players` — Los 11 jugadores alineados

```sql
CREATE TABLE lineup_players (
    id              SERIAL PRIMARY KEY,
    lineup_id       INT      NOT NULL REFERENCES lineups(id) ON DELETE CASCADE,
    player_id       INT      NOT NULL REFERENCES players(id),
    position_slot   VARCHAR(3) NOT NULL,  -- POR, DEF, MED, DEL (posición en la formación)
    display_order   SMALLINT NOT NULL,    -- Orden de visualización (1-11)
    points          SMALLINT DEFAULT 0,   -- Puntos de este jugador en esta jornada
    UNIQUE(lineup_id, player_id),
    UNIQUE(lineup_id, display_order)
);
```

**Diferencia con MySQL**: `alineaciones_temp` tenía todos los jugadores de la plantilla con un flag `alineado`. Ahora solo se guardan los 11 alineados en una estructura normalizada.

---

### 15. `participant_matchday_scores` — Puntuación de cada participante por jornada

```sql
CREATE TABLE participant_matchday_scores (
    id              SERIAL PRIMARY KEY,
    participant_id  INT      NOT NULL REFERENCES season_participants(id),
    matchday_id     INT      NOT NULL REFERENCES matchdays(id),
    total_points    SMALLINT NOT NULL DEFAULT 0,
    ranking         SMALLINT,  -- Puesto en esa jornada (para cálculo de pago semanal)
    UNIQUE(participant_id, matchday_id)
);
```

---

### 16. `transactions` — Movimientos económicos

```sql
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
CREATE INDEX idx_transactions_season ON transactions(season_id);
```

---

### 17. `competitions` — Preparada para futuro (playoffs, copa)

```sql
CREATE TABLE competitions (
    id              SERIAL PRIMARY KEY,
    season_id       INT          NOT NULL REFERENCES seasons(id),
    name            VARCHAR(100) NOT NULL,
    type            VARCHAR(20)  NOT NULL,  -- 'league' | 'playoff' | 'cup'
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
    config          JSONB,  -- Configuración flexible (formato, rondas, etc.)
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

**Nota**: No se implementa ahora. Solo existe la estructura para no tener que rediseñar cuando lleguen playoffs y copa.

---

### 18. `valid_formations` — Formaciones permitidas

```sql
CREATE TABLE valid_formations (
    id              SERIAL PRIMARY KEY,
    formation       VARCHAR(10) NOT NULL UNIQUE,
    defenders       SMALLINT    NOT NULL,
    midfielders     SMALLINT    NOT NULL,
    forwards        SMALLINT    NOT NULL
);

-- Datos fijos
INSERT INTO valid_formations (formation, defenders, midfielders, forwards) VALUES
('1-3-4-3', 3, 4, 3),
('1-3-5-2', 3, 5, 2),
('1-4-4-2', 4, 4, 2),
('1-4-3-3', 4, 3, 3),
('1-5-4-1', 5, 4, 1),
('1-5-3-2', 5, 3, 2);
```

---

## 🔄 Mapeo MySQL → PostgreSQL

| MySQL actual | PostgreSQL nuevo | Notas |
|---|---|---|
| `temporadas` | `seasons` + `scoring_rules` + `season_payments` | Normalizado y extensible |
| `usuarios_temp` | `users` + `season_participants` | Usuario único, participa en N temporadas |
| `equipos` | `teams` | Ahora vinculado a temporada |
| *(no existía)* | `players` | Tabla independiente con FK a equipo y dueño |
| `jornadas_temp` | `player_stats` + `lineups` + `lineup_players` | Separados: stats reales vs alineación fantasy |
| `alineaciones_temp` | `lineups` + `lineup_players` | Normalizado, solo los 11 alineados |
| `list_jornadas_temp` | `matchdays` + `matches` | Jornada ≠ partido, ahora separados |
| `vpv_audit` | *(campo en seasons)* | Innecesario con el nuevo modelo |
| *(no existía)* | `drafts` + `draft_picks` | Sistema completo de draft |
| *(no existía)* | `transactions` | Sistema económico |
| *(no existía)* | `competitions` | Preparado para playoffs/copa |
| *(no existía)* | `scoring_rules` | Puntuación configurable |
| *(no existía)* | `valid_formations` | Validación de formaciones |

---

## 📊 Consultas tipo (para validar el modelo)

### Clasificación general de una temporada
```sql
SELECT u.display_name,
       SUM(pms.total_points) as total_points,
       COUNT(pms.id) as matchdays_played
FROM participant_matchday_scores pms
JOIN season_participants sp ON sp.id = pms.participant_id
JOIN users u ON u.id = sp.user_id
JOIN matchdays md ON md.id = pms.matchday_id
WHERE sp.season_id = :season_id
  AND md.counts = TRUE
GROUP BY u.display_name
ORDER BY total_points DESC;
```

### Puntuación detallada de un participante en una jornada
```sql
SELECT p.display_name, p.position, t.name as team,
       ps.pts_total, ps.pts_play, ps.pts_starter, ps.pts_result,
       ps.pts_clean_sheet, ps.pts_goals, ps.pts_assists,
       ps.goals, ps.assists, ps.minutes_played
FROM lineup_players lp
JOIN lineups l ON l.id = lp.lineup_id
JOIN players p ON p.id = lp.player_id
JOIN teams t ON t.id = p.team_id
JOIN player_stats ps ON ps.player_id = p.id AND ps.matchday_id = l.matchday_id
WHERE l.participant_id = :participant_id
  AND l.matchday_id = :matchday_id
ORDER BY lp.display_order;
```

### Balance económico de un participante
```sql
SELECT type,
       SUM(amount) as total
FROM transactions
WHERE participant_id = :participant_id
  AND season_id = :season_id
GROUP BY type;
```

### Historial de draft (orden de elección)
```sql
SELECT dp.pick_number, dp.round_number,
       u.display_name as participant,
       p.display_name as player, p.position, t.name as team
FROM draft_picks dp
JOIN drafts d ON d.id = dp.draft_id
JOIN season_participants sp ON sp.id = dp.participant_id
JOIN users u ON u.id = sp.user_id
JOIN players p ON p.id = dp.player_id
JOIN teams t ON t.id = p.team_id
WHERE d.season_id = :season_id AND d.phase = 'preseason'
ORDER BY dp.pick_number;
```

---

## 🔑 Resumen: 18 tablas

| # | Tabla | Propósito |
|---|---|---|
| 1 | `users` | Identidad única |
| 2 | `seasons` | Configuración temporada |
| 3 | `scoring_rules` | Reglas de puntuación configurables |
| 4 | `season_payments` | Configuración económica |
| 5 | `season_participants` | Participantes por temporada |
| 6 | `teams` | Equipos por temporada |
| 7 | `players` | Jugadores por temporada |
| 8 | `drafts` | Eventos de draft |
| 9 | `draft_picks` | Elecciones del draft |
| 10 | `matchdays` | Jornadas |
| 11 | `matches` | Partidos |
| 12 | `player_stats` | Stats + puntos calculados por jugador/jornada |
| 13 | `lineups` | Alineación del participante por jornada |
| 14 | `lineup_players` | 11 jugadores alineados |
| 15 | `participant_matchday_scores` | Puntuación del participante por jornada |
| 16 | `transactions` | Movimientos económicos |
| 17 | `competitions` | Futuro: playoffs, copa |
| 18 | `valid_formations` | Formaciones permitidas |
