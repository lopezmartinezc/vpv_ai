# Brief para Claude Project — "Qué estadísticas usar para valorar jugadores en el draft VPV"

> Este documento es **autocontenido**. Cópialo entero al "Custom Instructions"
> del Claude Project. No necesitas adjuntar nada más para que Claude entienda
> el problema y proponga un sistema de valoración robusto.

---

## 1. Contexto: qué es VPV Fantasy

Liga VPV es una **liga fantasy de fútbol entre amigos** basada en La Liga
española de Primera División. ~13 participantes. Cada uno tiene una plantilla
de 26 jugadores reales, alinea 11 cada jornada (1 portero + 10 de campo en
una de 7 formaciones válidas) y gana puntos según el rendimiento real de esos
jugadores en cada jornada de Liga.

Hay dos drafts por temporada:
- **Pretemporada**: cada participante elige 26 jugadores en sistema serpiente.
- **Invierno** (mediados de temporada): cada uno puede soltar y fichar
  hasta 5 jugadores en sistema lineal.

Mi objetivo (Carlos): preparar el draft de la siguiente temporada de Liga
(septiembre 2026) decidiendo a qué estadísticas debo dar peso para identificar
los mejores picks **antes** de que la nueva temporada empiece.

---

## 2. Sistema de puntuación (lo que hay que predecir)

Cada jornada un jugador suma puntos así:

### Participación
- Jugar el partido: **+1**
- Titular (sale de inicio o juega 90'): **+1**

### Resultado del equipo
- Victoria: **+2**, Empate: **+1**, Derrota: **0**

### Goles (depende de posición)
| POR | DEF | MED | DEL |
|---|---|---|---|
| +10 | +8 | +7 | +5 |

### Portería a cero
- Portero con 0 goles encajados (≥65'): **+4**.
- Portero con 1 gol: 0. Con >1: penalización igual al número de goles
  encajados (3 goles = **-3**).
- Defensa con 0 goles encajados (≥45'): **+3**.
- MED y DEL: no reciben.

### Acciones positivas
- Gol de penalti: **+5**
- Asistencia: **+2**
- Penalti parado (POR): **+5**
- Tiro al palo: **+1**
- Penalti forzado: **+1**

### Acciones negativas
- Penalti fallado: **-3**
- Gol en propia meta: **-2**
- Tarjeta amarilla: **-1**
- Doble amarilla / Roja directa: **-3**
- Penalti cometido: **-1**

### Valoración mediática (importante)
- **Nota Marca** (1-4 estrellas): +1 / +2 / +3 / +4. "-" (no jugó): **-1**.
- **Picas AS** (cada pica = +1; pueden ser varias). "-": **-1**.

> Las puntuaciones exactas son configurables por temporada en la tabla
> `scoring_rules`. La estructura no cambia entre temporadas.

---

## 3. Datos disponibles para entrenar / razonar

### Histórico
- **8 temporadas completas** de La Liga (15-16 a 23-24 — IDs internos 1..8)
  con estadísticas por jornada. La temporada en curso (24-25, ID=9) está a
  punto de cerrarse cuando arranque el draft.
- **224.609 filas** de `player_stats`. Una por (jugador, jornada).
- **6.344 jugadores** acumulados (con altas/bajas entre temporadas).
- **3.039 partidos**.
- Para evitar el "drift" de reglas: el sistema de scoring ha cambiado de
  forma significativa antes de la temporada 5. Para backtest preseason
  uso **sólo seasons 5-8**.

### Columnas de `player_stats` (per jugador per jornada)

**Raw events** (lo que pasó en el partido):
- `goals`, `penalty_goals`, `penalties_missed`, `own_goals`, `assists`
- `penalties_saved`, `penalties_won`, `penalties_committed`
- `yellow_card`, `double_yellow`, `red_card`, `yellow_removed`
- `woodwork` (tiros al palo)
- `minutes_played`, `played` (bool), `event`/`event_minute` (suplencias)

**Resultado del equipo en ese partido**:
- `home_score`, `away_score`, `result` (-1 derrota, 0 empate, 1 victoria),
  `goals_for`, `goals_against`

**Calificación mediática**:
- `marca_rating` (string: "1"-"4", "-", "SC")
- `as_picas` (string: número de picas)

**Puntos calculados** (suman a la jornada del jugador):
- `pts_play`, `pts_starter`, `pts_result`, `pts_clean_sheet`,
- `pts_goals`, `pts_penalty_goals`, `pts_assists`, `pts_penalties_saved`,
- `pts_woodwork`, `pts_penalties_won`, `pts_penalties_missed`,
- `pts_own_goals`, `pts_yellow`, `pts_red`, `pts_pen_committed`,
- `pts_marca`, `pts_as`, `pts_marca_as`
- `pts_total` ← **TARGET principal** para predecir cuánto rendirá

**Position**: `position` ∈ {POR, DEF, MED, DEL}. Es la posición JUGADA en esa
jornada (no la nominal); se usa para calcular los puntos correctamente.

### Datos derivables fácilmente
- **Average puntos/partido** total, por posición, por temporada.
- **EWMA** de últimas N jornadas (medida de "forma").
- **Coefficient of variation** (desviación / media): proxy de regularidad.
- **G+A por 90**: goles + asistencias normalizados por minutos.
- **Starter pct** últimas N jornadas: titularidad estable.
- **Calidad del equipo**: agregado de puntos del equipo en la temporada.
- **Career trend**: pendiente de avg_pts contra el año (subiendo / bajando).
- **Second half avg** (J20-J38): el cierre fuerte de temporada suele
  carry-over al año siguiente.
- **Edad**: NO está en BBDD; podríamos enriquecerla manualmente para los
  picks top-100 si crees que ayuda.

---

## 4. Modelos ya backtested

Ya tenemos un sistema en producción que prueba varios modelos contra picks
reales históricos. Métricas de evaluación:

- **Spearman correlation**: relación entre la predicción del modelo y el
  rendimiento real (avg_pts) de la temporada siguiente. 1.0 = perfecto. >0.7
  es muy bueno.
- **MAE**: mean absolute error en puntos/partido.
- **Bust rate**: % de picks "top recomendados" que rindieron por debajo de la
  media. <15% es bueno.
- **Top26 hit rate**: % de los top-26 del modelo que realmente acaban en el
  top-26 del rendimiento real.

### Ranking actual (preseason, seasons 5-8)

| ID | Modelo | Spearman | Descripción |
|---|---|---|---|
| **V** | Ensemble diverso | **0.718** ⭐ | Media de: simple avg + minutes stability + career trend + 2nd half form |
| R | Team quality | 0.713 | Pondera por la calidad del equipo de cada jugador |
| W | Position specific | 0.713 | Pesos distintos por posición (más asistencias para MED, más portería a cero para POR/DEF) |
| H | 2nd half form | 0.712 | Solo pondera el rendimiento de J20-J38 (cierre fuerte = arranque fuerte) |
| I | Productivity | 0.712 | G+A por 90 boosted |
| U | Ensemble top-3 | 0.712 | Media de los 3 mejores submodels |
| A | Simple average | 0.711 | Baseline — sólo `avg(pts_total)` last season |
| K | Minutes stability | 0.710 | Premia titulares fijos |

Spreads tan estrechos sugieren que el techo del backtest está cerca y que la
ganancia marginal de añadir features es pequeña. Las decisiones difíciles
están en las colas (jugadores nuevos a la liga, cambios de club, lesiones).

### Para draft de invierno (con season parcial)

| ID | Modelo | Spearman |
|---|---|---|
| W1 | Winter simple | **0.926** |

El invierno es mucho más predecible porque ya tienes ~19 jornadas de la
temporada en curso, que es mucho más informativa que el cierre del año
anterior.

---

## 5. Lo que quiero que hagas

Estoy preparando el draft de pretemporada de la Liga 25-26. Tengo:
- 8 temporadas históricas completas.
- 1 temporada actual (24-25) cuyos datos estarán cerrados antes del draft.
- ~600 jugadores activos en La Liga que potencialmente podrían ser
  pickeados.

### Mi pregunta para Claude

1. **Dado el sistema de puntuación de arriba, ¿qué métricas son las que
   realmente explican `pts_total`?** Para cada posición. (Spoiler: para POR
   probablemente sea "ratio de victorias y porterías a cero del equipo";
   para MED es "asistencias + Marca"; etc — quiero que lo razones).

2. **¿Qué features debería derivar de los raw stats que el modelo V
   (Ensemble) no esté usando todavía?** Ejemplos que ME interesan
   especialmente:
   - **Quality of opposition adjusted**: ¿los puntos contra rivales fuertes
     pesan más?
   - **Expected goals (xG / xA)** si pudiera obtenerlos de otra fuente.
   - **Tiempo cumulativo jugando**: minutes burnout.
   - **Histórico de lesiones**: hay algún campo de availability pero quizás
     se pueda enriquecer.
3. **¿Qué señales son "trampa"?** Stats que parecen útiles pero no predicen
   bien la siguiente temporada (ej: tarjetas mucho — alta variabilidad,
   sample size pequeño).
4. **¿Cómo separamos "bueno por talento" de "bueno por entorno"?** Los
   jugadores que cambian de equipo top → bottom (o viceversa) son el caso
   más difícil. Qué métrica usar para detectarlo a tiempo.
5. **¿Hay alguna trampa con el target `pts_total` del histórico?** Por
   ejemplo: jugadores que ya no juegan en La Liga (retirados / Premier /
   transfers fuera) pero siguen en la BBDD con stats antiguos.

### Lo que NO quiero (déjalo claro a Claude)

- No quiero un sistema de ML "caja negra" más complejo. Los modelos
  lineales/ensembles han topado en ~0.72 Spearman y eso es bastante. Quiero
  **insights sobre qué métricas mirar** para decidir picks como humano,
  potencialmente con apoyo del modelo.
- No quiero recomendaciones que requieran datos que no tengo (xG por
  ejemplo, salvo que me digas DÓNDE conseguirlos limpios).
- No quiero un análisis sólo de los top-10 jugadores — esos son obvios.
  Quiero foco en **el corte del round 4-8** del draft, donde se ganan o
  pierden las temporadas.

---

## 6. Sobre la implementación final

Tras el análisis, los outputs útiles serán:

1. **Una matriz de "qué métricas pesan más por posición"** con una
   propuesta de pesos justificada por correlación contra `pts_total` de la
   temporada siguiente.
2. **Una lista de features derivadas a añadir** al pipeline de
   `service_draft.py` (en VPV ya existen los modelos backtested; añadir
   features es viable).
3. **Una "scorecard mental"** que pueda aplicar yo a mano cuando dude entre
   2 picks reales (qué 3-5 números mirar y en qué orden).
4. **Recomendaciones de qué tipos de jugadores históricamente son trampa**
   ("ese veterano top scorer de equipo descendido que ficha por uno top — no
   suele rendir igual"). Casos concretos sin nombres, sólo perfiles.

Cuando empieces, primero pregúntame **qué temporadas concretas voy a poder
estudiar y cuánto detalle puedes verificar contra el código de
`service_draft.py`**. Quiero un análisis honesto sobre los límites de la
muestra (8 temporadas con cambios de reglas es poco).
