# Estadisticas Avanzadas — Liga VPV Fantasy

Guia completa de todas las metricas del modulo de estadisticas avanzadas. Cada seccion explica **que mide**, **como se calcula** y **como interpretarla** en el contexto de una liga fantasy.

---

## Fase 1: Valoracion Individual

Metricas que evaluan el rendimiento real de cada jugador mas alla de la simple media de puntos.

### PPM (Puntos Por Partido)

- **Que mide**: El rendimiento medio por jornada jugada.
- **Formula**: `total_points / matchdays_played`
- **Interpretacion**: Es la metrica base. Un jugador con PPM 8.0 promedia 8 puntos cada vez que juega. Sin embargo, por si sola no dice nada sobre la fiabilidad de esa media — un jugador puede tener PPM 8.0 con jornadas de 2, 14, 8, 8 (volatil) o con 7, 8, 9, 8 (consistente).

### σ (Desviacion Estandar)

- **Que mide**: La volatilidad o dispersion de las puntuaciones respecto a la media.
- **Formula**: `STDDEV_SAMP(pts_total)` — desviacion estandar muestral.
- **Interpretacion**: Cuanto mayor es σ, mas impredecible es el jugador. Un σ de 2 significa que la mayoria de sus puntuaciones caen dentro de ±2 puntos de su media. Un σ de 8 indica un jugador "boom or bust" — puede darte 20 puntos o -2.
- **Ejemplo**: Jugador A (media 7, σ=2) es mucho mas fiable que Jugador B (media 7, σ=6), aunque ambos promedien lo mismo.

### CV (Coeficiente de Variacion)

- **Que mide**: La consistencia normalizada — permite comparar volatilidad entre jugadores con medias distintas.
- **Formula**: `σ / PPM`
- **Interpretacion**:
  - CV < 0.3 → **Consistente** (verde). El jugador rinde de forma predecible.
  - CV 0.3–0.5 → **Moderado** (amarillo). Variabilidad normal.
  - CV > 0.5 → **Volatil** (rojo). Rendimiento muy impredecible.
- **Por que no basta con σ**: Un portero con media 3 y σ=2 (CV=0.67) es muy volatil para su nivel, mientras que un delantero con media 12 y σ=4 (CV=0.33) es bastante consistente a pesar de tener mayor σ absoluta.

### Percentiles (P10 / P50 / P90)

- **Que miden**: El "suelo", la mediana y el "techo" de rendimiento del jugador.
- **Formula**: `PERCENTILE_CONT(0.10/0.50/0.90)` sobre la distribucion de pts_total.
- **Interpretacion**:
  - **P10 (suelo)**: El 10% de sus peores jornadas puntua por debajo de este valor. Responde a: "¿Cual es su peor dia tipico?"
  - **P50 (mediana)**: El valor central de sus puntuaciones. A diferencia de la media, no se distorsiona por valores extremos.
  - **P90 (techo)**: Solo el 10% de sus jornadas supera este valor. Responde a: "¿Cual es su mejor dia tipico?"
- **Uso practico**: Si necesitas un jugador seguro para tu alineacion, busca P10 alto. Si necesitas un "lottery ticket" que pueda explotar, busca P90 alto (aunque tenga P10 bajo).

### pp90 (Puntos Por 90 Minutos)

- **Que mide**: Eficiencia ajustada por tiempo de juego.
- **Formula**: `(Σ pts_total / Σ minutes_played) × 90`
- **Interpretacion**: Normaliza el rendimiento a un partido completo de 90 minutos. Es especialmente util para:
  - **Suplentes habituales**: Un jugador que entra 30 minutos y marca 5 puntos tiene pp90 = 15, revelando que es muy eficiente cuando juega.
  - **Titulares indiscutibles**: Normalmente pp90 ≈ PPM porque juegan ~90 minutos.
  - **Comparar justamente**: Permite comparar un suplente que juega 20 minutos con un titular que juega 90.
- **Advertencia**: pp90 puede ser engañoso con muestras muy pequeñas (ej: un jugador que jugo 10 minutos y marco un gol tendra pp90 astronomico).

### CI 95% (Intervalo de Confianza al 95%)

- **Que mide**: El rango dentro del cual esta la "verdadera media" del jugador con un 95% de confianza.
- **Formula**: `PPM ± t(n-1) × σ / √n`
  - `t(n-1)` es el valor de la distribucion t de Student para n-1 grados de libertad (tabla precalculada, no requiere scipy).
  - `n` es el numero de partidos jugados.
  - `σ` es la desviacion estandar.
- **Interpretacion**: Si un jugador tiene CI [6.2, 9.8], significa que su rendimiento real medio esta probablemente entre 6.2 y 9.8 puntos.
  - **CI estrecho** (ej: [7.5, 8.5]) → Muchos partidos jugados, alta confianza en la media. Sabes lo que va a rendir.
  - **CI amplio** (ej: [3.0, 13.0]) → Pocos partidos o mucha volatilidad. La media es poco fiable.
- **Uso en draft**: Entre dos jugadores con PPM similar, el que tenga CI mas estrecho es la apuesta mas segura.

### Form₅ (Forma Reciente)

- **Que mide**: El rendimiento ponderado de las ultimas 5 jornadas, dando mas peso a las mas recientes.
- **Formula**: EWMA (Exponentially Weighted Moving Average) con α=0.3:
  ```
  form = valor_jornada_1
  form = 0.3 × valor_jornada_2 + 0.7 × form
  form = 0.3 × valor_jornada_3 + 0.7 × form
  ...
  ```
  Los pesos efectivos son: jornada mas reciente ~30%, anterior ~21%, siguiente ~15%, etc.
- **Interpretacion**: Captura la tendencia reciente mejor que una media simple de las ultimas 5 jornadas, porque pondera mas lo reciente. Un jugador con Form₅ = 12 pero PPM = 8 esta en racha ascendente.
- **Requisito**: Se necesitan al menos 5 jornadas jugadas. Con menos, se muestra como N/A.

### Trend (Tendencia)

- **Que mide**: La direccion del rendimiento reciente comparada con el historico.
- **Formula**:
  - Si `Form₅ > PPM × 1.1` → **Rising** (↑ verde): Rinde un 10%+ mejor que su media historica.
  - Si `Form₅ < PPM × 0.9` → **Falling** (↓ rojo): Rinde un 10%+ peor que su historico.
  - En otro caso → **Stable** (→ gris): Rinde acorde a su media.
- **Uso practico**: Antes de alinear, revisa tendencias. Un jugador "stable" es predecible, un "rising" puede ser buena apuesta, un "falling" podria necesitar banquillo.

---

## Fase 2: Analisis por Posicion

Metricas que evaluan el valor relativo de los jugadores dentro de cada posicion, respondiendo a la pregunta clave del draft: "¿En que posicion hay mas escasez de talento?"

### Replacement Level (Nivel de Reemplazo)

- **Que mide**: La puntuacion del "siguiente mejor jugador disponible" en cada posicion.
- **Formula**: Se ordenan todos los jugadores de una posicion por puntos totales descendentes. El nivel de reemplazo es la puntuacion del jugador N+1, donde N es el numero tipico de jugadores drafteados en esa posicion (basado en formaciones habituales × numero de participantes).
  - **POR**: N = numero de participantes (cada uno necesita 1 portero + suplentes)
  - **DEF**: N = participantes × 4 (formaciones tipicas llevan 4 defensas)
  - **MED**: N = participantes × 4
  - **DEL**: N = participantes × 2
- **Interpretacion**: Si el replacement level de DEL es 80 puntos y el de MED es 120, significa que los delanteros "gratis" (no drafteados) rinden peor que los mediocampistas gratis. Un delantero con 100 puntos esta 20 por encima del reemplazo → es valioso. Un mediocampista con 100 esta 20 por debajo → no merece un pick alto.

### PAR (Points Above Replacement)

- **Que mide**: Cuantos puntos aporta un jugador por encima del nivel de reemplazo de su posicion.
- **Formula**: `total_points - replacement_level`
- **Interpretacion**:
  - PAR > 0: El jugador rinde mas que un "jugador gratis". Merece ser drafteado.
  - PAR = 0: Rinde igual que el reemplazo. Da igual tenerlo o no.
  - PAR < 0: Rinde peor que un jugador sin draftear. Candidato a soltar.
- **Uso en draft**: PAR permite comparar jugadores de distintas posiciones. Un DEL con PAR 50 es mas valioso que un MED con PAR 30, independientemente de sus puntos totales absolutos.

### Tiers (Niveles)

- **Que mide**: Clasificacion de jugadores en 4 categorias basadas en rendimiento relativo dentro de su posicion.
- **Formula**: Basada en percentiles de la distribucion de puntos totales:
  - **Tier 1 — Elite** (percentil ≥ 90): Top 10% de la posicion.
  - **Tier 2 — Solido** (percentil 75–89): Por encima de la media, fiables.
  - **Tier 3 — Promedio** (percentil 50–74): Rinden en la media.
  - **Tier 4 — Reemplazable** (percentil < 50): Por debajo de la media, sustituibles.
- **Interpretacion**: En el draft, quieres maximizar jugadores Tier 1-2 y evitar gastar picks en Tier 4.

### Scarcity Index (Indice de Escasez)

- **Que mide**: Que tan dificil es encontrar jugadores elite en cada posicion.
- **Formula**: `jugadores_tier_1 / total_jugadores_posicion`
- **Interpretacion**: Un indice de escasez bajo (ej: 0.05 para porteros) indica que hay muy pocos porteros elite — si pierdes la oportunidad de draftear uno, no hay alternativas. Un indice alto (ej: 0.15 para mediocampistas) sugiere que hay mas opciones de calidad.
- **Uso en draft**: Prioriza draftear posiciones con mayor escasez primero. Si los delanteros tienen escasez 0.04 y los mediocampistas 0.12, los delanteros elite se agotan antes.

---

## Fase 3: Historial de Draft

Metricas que analizan el rendimiento historico de los picks del draft cruzando multiples temporadas, respondiendo a: "¿Que picks dan mejor resultado?"

### Pick Value Curve (Curva de Valor por Pick)

- **Que mide**: El rendimiento medio historico de cada numero de pick del draft.
- **Formula**: Para cada pick_number (1, 2, 3, ..., N): `AVG(total_season_points)` cruzando todas las temporadas disponibles.
- **Interpretacion**: La curva deberia ser descendente — picks tempranos (#1, #2, #3) deberian rendir mas que picks tardios (#20, #25). Pero no siempre es lineal:
  - **Mesetas**: Picks 5-10 pueden rendir similar si la calidad es homogenea en ese rango.
  - **Anomalias**: Si pick #15 rinde mas que pick #8 historicamente, sugiere que la posicion 8-14 esta sobrevalorada.
- **Uso practico**: Ayuda a decidir si un trade de picks merece la pena. Si el pick #3 historicamente da ~200 puntos y el #12 da ~150, conoces la "diferencia esperada" al intercambiar.

### Position by Round (Posicion por Ronda)

- **Que mide**: Que posiciones rinden mejor segun la ronda en que se draftearon.
- **Formula**: Para cada combinacion (ronda, posicion): `AVG(total_season_points)` y `count(picks)`.
- **Interpretacion**: Presentada como heatmap con colores:
  - **Verde intenso**: Combinaciones con alto rendimiento medio (ej: DEL en ronda 1).
  - **Rojo**: Combinaciones con bajo rendimiento (ej: POR en ronda 1 = pick desperdiciado).
- **Uso en draft**: Si los delanteros drafteados en ronda 3 rinden casi igual que en ronda 1, no merece la pena "quemar" un pick temprano en delantero.

### Bust Rate (Tasa de Fracaso)

- **Que mide**: Que porcentaje de picks de rondas tempranas (1-3) terminaron rindiendo por debajo del nivel de reemplazo de su posicion.
- **Formula**: `picks_bajo_replacement / total_picks_rondas_1_a_3 × 100`
- **Interpretacion**: Un bust rate alto en rondas tempranas indica que las primeras elecciones son arriesgadas — muchos jugadores "estrella" no cumplen expectativas. Si la tasa es 25%, uno de cada cuatro picks de primera ronda es un fracaso.
- **Desglose**: Se muestra por rangos de rondas para ver si el riesgo se concentra en alguna ronda especifica.

### Steal Rate (Tasa de Hallazgo)

- **Que mide**: Que porcentaje de picks tardios (rondas 20+) terminaron superando la mediana de su posicion.
- **Formula**: `picks_sobre_mediana / total_picks_rondas_20_plus × 100`
- **Interpretacion**: Un steal rate alto indica que hay oportunidades de encontrar gemas ocultas en rondas tardias. Si la tasa es 15%, uno de cada seis-siete picks tardios resulta ser una sorpresa positiva.
- **Uso practico**: Si la steal rate es consistentemente alta, merece la pena investigar jugadores en rondas tardias en vez de asumir que ya no queda nada bueno.

---

## Fase 4: Analisis Contextual

Metricas que anaden contexto situacional al rendimiento de los jugadores.

### Home/Away Splits (Rendimiento Local/Visitante)

- **Que mide**: Si un jugador rinde diferente jugando en casa vs fuera.
- **Formula**: Se agrupan las jornadas segun si el equipo del jugador jugo como local o visitante:
  - `location = "home"` si `match.home_team_id == player.team_id`
  - `location = "away"` en caso contrario
  - Para cada grupo: `AVG(pts_total)`, `SUM(pts_total)`, `COUNT(matches)`, `SUM(goals)`, `SUM(assists)`
- **Interpretacion**: Algunos jugadores rinden significativamente mejor en casa (campo conocido, aficion) o fuera. Si un jugador tiene media 10 en casa y 5 fuera, conviene alinearlo solo en jornadas de local.
- **Uso practico**: Antes de cada jornada, revisa si tu jugador juega en casa o fuera y consulta sus splits para decidir si alinearlo.

### Team Dependency (Dependencia de Equipo)

- **Que mide**: Que porcentaje de los puntos fantasy totales de un equipo real aporta su mejor jugador.
- **Formula**:
  1. Para cada equipo, sumar los `pts_total` de todos sus jugadores en la temporada.
  2. Identificar al jugador con mas puntos del equipo.
  3. `dependency_pct = top_player_points / team_total_points × 100`
- **Interpretacion**:
  - **Dependencia alta** (>30%): El equipo depende enormemente de un jugador. Si ese jugador se lesiona, los demas jugadores del equipo probablemente rendiran peor (menos goles del equipo → menos puntos por resultado).
  - **Dependencia baja** (<15%): Los puntos estan repartidos. El equipo es mas resiliente.
- **Uso en draft**: Evita tener multiples jugadores de un equipo con alta dependencia si no tienes al jugador estrella. Si tienes al estrella, puedes complementar con compañeros que se benefician de su rendimiento.

### Radar de Comparacion (Player Comparison)

- **Que mide**: Perfil multidimensional de hasta 3 jugadores comparados en 6 ejes.
- **Ejes del radar**:

| Eje | Formula | Que valora |
|-----|---------|------------|
| **Goles** | `goals / matches_played`, normalizado 0-100 | Capacidad goleadora por partido |
| **Asistencias** | `assists / matches_played`, normalizado 0-100 | Capacidad de generar juego |
| **Media** | `avg_points`, normalizado 0-100 | Rendimiento medio global |
| **Consistencia** | `1 - CV`, normalizado 0-100 | Fiabilidad (inverso de volatilidad) |
| **pp90** | Puntos por 90 min, normalizado 0-100 | Eficiencia por tiempo jugado |
| **Forma** | Form₅ (EWMA), normalizado 0-100 | Rendimiento reciente |

- **Normalizacion**: Cada eje se escala de 0 a 100 relativo al maximo entre los jugadores comparados. Si el Jugador A tiene la mejor tasa de goles, su eje "Goles" sera 100 y los demas se escalaran proporcionalmente.
- **Interpretacion del grafico**: El area del poligono refleja el rendimiento general. Un poligono grande y equilibrado indica un jugador completo. Un poligono con picos indica un especialista.
- **Uso practico**: Ideal para decidir entre jugadores similares antes del draft o al elegir quien alinear. Compara perfiles para ver quien es mas goleador, quien mas consistente, quien esta en mejor forma.

---

## Filtros Disponibles

Todas las metricas de Fase 1 permiten filtrar por:
- **Posicion**: POR, DEF, MED, DEL — para comparar dentro de la misma posicion.
- **Minimo de partidos** (min_played): Por defecto 3. Filtra jugadores con pocas jornadas para evitar metricas distorsionadas (ej: un jugador con 1 partido y 15 puntos tendria PPM 15 pero no es representativo).
- **Busqueda por nombre**: Para encontrar jugadores especificos.

---

## Glosario Rapido

| Sigla | Nombre completo | En una frase |
|-------|----------------|--------------|
| PPM | Puntos Por Partido | Media simple de puntos |
| σ | Desviacion Estandar | Volatilidad absoluta |
| CV | Coeficiente de Variacion | Volatilidad relativa a la media |
| P10/P50/P90 | Percentiles | Suelo / mediana / techo |
| pp90 | Puntos Por 90 Minutos | Eficiencia temporal |
| CI 95% | Intervalo de Confianza | Rango probable de la media real |
| EWMA | Media Movil Exponencial | Promedio ponderando lo reciente |
| PAR | Points Above Replacement | Valor sobre el nivel gratuito |
| Scarcity | Indice de Escasez | Dificultad de encontrar elite |
| Bust | Fracaso | Pick caro que no rindio |
| Steal | Hallazgo | Pick barato que sorprendio |
