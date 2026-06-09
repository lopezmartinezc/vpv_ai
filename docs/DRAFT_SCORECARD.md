# Scorecard mental — Draft pretemporada VPV

> **Origen**: análisis hecho en un Claude Project externo sobre seasons 6-8
> (23-24 a 25-26), jugadores con ≥10 partidos. Umbrales = percentiles reales
> por posición. Generado en junio 2026 — guardado aquí para que esté
> disponible cuando arranque el draft de septiembre.

Para decidir a mano entre 2 picks reales. Los números son percentiles reales
de cada posición.

---

## Principio rector (vale para todo)

El sistema premia el **SUELO** (jugar + titular + resultado del equipo + nota
Marca/AS), que es el **81-98%** de la puntuación. El **techo** (goles,
asistencias, portería a cero) es propina. Consecuencia operativa:

> La disponibilidad y el rol mandan sobre el talento. Un titular fijo
> mediocre de un equipo decente puntúa más que un crack que juega media
> temporada. El draft no premia quién es mejor, premia **quién juega 90' en
> un equipo que gana y le ponen buena nota**.

Y el modelo es **ciego** a las dos cosas que más deciden el round 4-8:
- ¿va a jugar?
- ¿en qué equipo?

Esa es tu ventaja humana. Úsala primero.

---

## Paso 0 — Filtro universal ANTES de mirar posición

Aplica esto a cualquier duelo, sea cual sea la posición:

### ¿Es titular blindado?

| Métrica | p25 | p50 | p75 |
|---|---|---|---|
| Partidos jugados (de 38) | 17 | 22 | **27** |
| Starter rate | 0.56 | 0.79 | **0.93** |

→ Si uno juega **≥27 partidos** y el otro ronda 17-20, **se acabó el duelo**:
coge al que juega. El suelo decide.

### ¿Hay competencia por su puesto o riesgo de rotación/lesión recurrente?

El modelo no lo ve. Si tú sí lo sabes, **pesa más que cualquier número**.

Solo si empatan en disponibilidad, pasas a la posición.

---

## POR — No valores al portero, valora al equipo

Su rendimiento individual del pasado **no predice nada** (correlación ≈0;
rango estrechísimo: p25=5.4, p90=7.6 — todos puntúan casi igual). Lo único
que mueve la aguja es la **portería a cero**, que es del equipo.

### Mira en este orden:

1. **Calidad defensiva del equipo al que jugará**. ¿Top-6 que encaja poco, o
   recién ascendido? Esto es el **90% de la decisión**.
2. **Titular #1 sin discusión** (¿hay segundo portero amenazante? ¿rotación
   en Copa?).
3. **(Desempate)** `avg_pts` previo — solo si los dos están en la misma
   situación de equipo. Tier: elite ≥6.5, normal ~5.9.

### Ignora

Paradas espectaculares, paradas de penalti, "es el mejor portero
técnicamente". **Ruido**.

---

## DEF — Equipo sólido + titular fijo, el gol es bonus

Predictores que sí valen: **nivel propio (0.43)** y **calidad de equipo
(0.29)**. La portería a cero (+3) viene del equipo, no de él.

### Mira en este orden:

1. **Titular fijo** (Paso 0).
2. **¿Equipo que defiende bien?** Más porterías a cero = más puntos pasivos.
3. **`avg_pts` previo**. Tier: elite ≥6.6, sólido ~5.8, relleno <4.9.
4. **(Desempate) Amenaza ofensiva**: un gol de defensa vale **+8** (más que
   el de un delantero). Laterales que asisten, centrales rematadores a
   balón parado. Esto SÍ separa a dos defensas con suelo parecido.

---

## MED — avg_pts manda; la media solo lo confirma

Particularidad clave: la nota Marca/AS **no es señal independiente** —
correlaciona **0.89 con el propio `avg_pts`** (los puntos de media son parte
del total). Sirve como confirmación, no como desempate.

### Mira en este orden:

1. **`avg_pts` previo**. Tier: bueno ≥6.1, normal ~5.3, flojo <4.4.
2. **Titularidad fija (0.39)** — el desempate real entre dos MED con
   `avg_pts` parecido. La media NO los separará (echa lo mismo que el
   `avg_pts`).
3. **(Desempate) G+A por 90** para creativos/llegadores + entorno (equipo
   que crea). El gol de MED vale **+7**.
4. **(Sanity check)** media Marca+AS p75 ≈ 2.69 — si es muy baja para su
   `avg_pts`, sospecha de un año inflado por otra vía.

---

## DEL — La posición más predecible y la más "de talento"

La única donde el rendimiento individual **manda de verdad** (`avg_pts`
0.56, el más alto) y la de **mayor rango** (p25=4.2 a p90=8.4 — aquí sí hay
cracks y hay trampas).

### Mira en este orden:

1. **`avg_pts` previo**. Tier: elite ≥7.2, medio ~5.4, trampa <4.2.
2. **Minutos / disponibilidad (0.49)** — un '9' que solo juega 20' no
   acumula.
3. **¿Es EL lanzador de penaltis?** Única posición donde importa (0.25).
   Vale **~+0.6 pts/partido (≈+15/temporada)**. OJO: el rol solo persiste el
   **44%** — no mires quién lanzó el año pasado, averigua **quién lanzará el
   que viene** en su equipo.
4. **(Desempate) G+A por 90 (0.33)** + **calidad de equipo (0.46)**: un
   delantero en equipo que crea mucho marca más.

---

## Overrides — aplícalos SIEMPRE al final, pueden tumbar todo lo anterior

### 🔻 Regresión desde un año-techo

Si la última fue su mejor temporada y muy por encima de su línea base
previa, **réstale ~0.7 pts mentalmente**. Dato: la mediana de un año top
(7.3) regresa a **6.6** al siguiente. Solo el **54%** de los top-cuartil
repiten; **el 46% se cae**. **No pagues el pico**.

### 🟰 La volatilidad NO es una trampa

El CV (regularidad) no predice nada (≈0). **No descartes a nadie por
"irregular"**. Importa la media, no la varianza.

### 🚫 Recién llegados a Liga = cero señal real

El modelo finge predecirlos (se autocorrelaciona). Trátalos como **alta
varianza**: una buena media temporada NO es base fiable. No los
sobre-draftees.

### 🕐 Fichaje de invierno = muestra fina (½ temporada)

Tiene datos de Liga pero solo ~14 partidos y en frío. Regresa más hacia la
media (no trates 14 partidos como 38) y aplícale un **haircut de
supervivencia más duro**: sobreviven el **51%** vs **61%** de los normales.
Son el ~9% del pool.

### 🚫 Tarjetas y eventos raros

(Palos, penaltis forzados): **no los peses**. Muestra pequeña, alta
variabilidad, peso unitario bajo.

### ⚠️ Cambio de equipo = re-proyecta el entorno

(Ver sección Q4 abajo). El número del año pasado lleva embutido el equipo
viejo. Si cambia de club, ese número **miente** — sobre todo para POR.

---

## Q4 — Ajuste por cambio de equipo (talento vs entorno)

**Idea clave (contraintuitiva)**: no restes el entorno para hallar "talento
puro" — eso predice **peor** (0.43 vs 0.52). El entorno es la parte **más
grande y persistente** de la puntuación. Para un jugador que sigue en su
club, su `avg_pts` crudo ya está bien. El ajuste **solo aplica a los que
cambian de equipo**: ahí re-proyectas el entorno nuevo sobre su talento.

### Cuánto se mueve el `avg_pts` por cada salto en calidad de equipo

(regresión intra-jugador)

| Pos | Sensibilidad |
|---|---|
| **POR** | ±1.9 pts — re-rátalo casi entero por el equipo nuevo |
| **DEL** | ±1.4 pts |
| **MED** | ±1.1 pts |
| **DEF** | ±0.8 pts |

### Receta para un mover

1. Parte de su `avg_pts` del año pasado.
2. **Δ ≈ sensibilidad_pos × (calidad_equipo_nuevo − calidad_equipo_viejo)**.
   Proxy de calidad = posición final en la tabla real: top-4 alto, mitad
   neutro, descenso/ascendido bajo.
3. Resta **~0.7 extra** si venía de su mejor año — los movers fichan justo
   tras un pico, así que regresan más.

**Ejemplo**: portero que pasa de top-4 a recién ascendido → su 6.5 del año
pasado proyecta más cerca de **~4.5-5.0**. No pagues el número viejo.

(Muestra: 434 pares, p<0.0001 para la pendiente general; solo 63 movers, así
que el número es la pendiente, no casos individuales.)

---

## Inputs externos — lo que el modelo NO puede ver (y tú sí)

El modelo ya tocó techo: todo lo derivable del histórico es ~`avg_pts`
disfrazado. Tu ventaja son tres cosas **de fuera del registro**:

1. **Disponibilidad / rol**. Es el mayor driver del valor
   (`avg_pts × partidos`) y es casi impredecible por stats (corr año a año =
   0.19). Resuélvela con info humana: profundidad de plantilla, competencia
   por el puesto, lesiones recurrentes, minutos de pretemporada. **Un crack
   que juega media temporada vale menos que un titular fijo del montón.**
2. **xG / xA (solo DEL)**. Des-suertea el techo ofensivo: un '9' que metió
   15 con 9 de xG regresará y el modelo no lo ve. **Fuente gratis: Understat
   (La Liga, por jugador/temporada).**
3. **Edad**. Curva de declive, sobre todo >30 (no porteros) y veteranos que
   cambian de equipo. Enriquécela a mano para el **top-100**.

### Lo que NO aporta señal nueva

- Media Marca/AS (colineal con `avg_pts`)
- Calidad de rival (calendario equilibrado)
- Volatilidad/tarjetas (ruido)

**No pierdas tiempo en ellas.**

---

## Q5 — Riesgo de supervivencia (el "haircut")

**40% de los drafteables no dan temporada drafteable al año siguiente**
(30% se van de Liga, 10% lesión/banquillo). El backtest solo ve al 60% que
sobrevive, así que el bust rate "<15%" es ficticio: es bust **entre
supervivientes**. El bust real (no darte nada) por tier:

| `avg_pts` | No sobrevive |
|---|---|
| >7 elite | 23% |
| 6-7 | 28% |
| 5-6 (R4-8) | 36% |
| <5 | 50% |

### Réstale a su valor proyectado un haircut por fragilidad antes de comparar

| Tier | Haircut |
|---|---|
| >7 elite | **−22%** |
| 6-7 | **−27%** |
| 5-6 (R4-8) | **−32%** |
| <5 | **−48%** |

Cuanto **más abajo** en el draft, **más castigas** la fragilidad. Y la
supervivencia **casi no se predice con stats** (corr 0.25) → palancas
externas: **edad, rumores de traspaso** (top de equipo medio que suena para
un grande = riesgo de irse), **historial de lesiones**. POR y DEL rotan más
(≈46-47%); MED es el más estable (34%).

---

## El duelo de 2 jugadores, en orden

1. **¿Misma disponibilidad?** Si no → coge al titular fijo. **Fin**.
2. **¿Misma posición y disponibilidad?** → compara la métrica #1 de esa
   posición (tiers de arriba).
3. **¿Siguen empatados?** → desempate específico: equipo (POR/DEF),
   titularidad fija (MED), penaltista del año que viene (DEL).
4. **Aplica overrides** → resta por año-pico (~0.7), por recién llegado,
   por haircut de supervivencia (−22% a −32% según tier) y re-proyecta el
   entorno de los movers.

---

## Regla de bolsillo

**Disponibilidad → nivel propio (tier) → entorno/equipo → desempate de
posición.**

Si memorizas solo eso, ya bates al modelo en su punto ciego.

---

## Referencias cruzadas

- [DRAFT_IMPROVEMENTS.md](DRAFT_IMPROVEMENTS.md) — plan de mejoras al draft
  live (septiembre 2026). Este scorecard alimenta directamente la Mejora 1
  (Ensemble en draft live) y la Mejora 2 (comparativa lateral): los tiers
  por posición se convierten en badges visuales.
- [CLAUDE_PROJECT_BRIEF_DRAFT_STATS.md](CLAUDE_PROJECT_BRIEF_DRAFT_STATS.md)
  — brief que usé para generar este análisis.
- [PLAYOFFS_DESIGN.md](PLAYOFFS_DESIGN.md) — sin relación, pero parte del
  contexto.

## Implicaciones para el código (notas para septiembre)

Al implementar la Mejora 1 de [DRAFT_IMPROVEMENTS.md](DRAFT_IMPROVEMENTS.md),
considerar:

1. **Tiers como badge visual**: cada card de jugador muestra su tier por
   posición (elite/sólido/normal/flojo) según los umbrales de este doc.
2. **Haircut de supervivencia** aplicado al `ensemble_score` antes de
   ordenar sugerencias por posición → los R4-8 reciben −32% del score
   anunciado.
3. **Flag de "mover"**: marcar jugadores que han cambiado de equipo desde
   la temporada anterior. Recomendar al admin: "este jugador cambió de
   equipo, su `avg_pts` puede engañar".
4. **Flag de "año pico"**: si la última fue su mejor temporada con
   diferencia, badge `🔻 regresion-risk` + `avg_pts - 0.7` mostrado entre
   paréntesis.
5. **Penaltista**: campo nuevo (manual al menos para top-100, o derivado
   automáticamente contando `penalty_goals + penalties_missed` >2 por
   temporada). Vale +15 pts/temporada solo para DEL.
6. **NO mostrar**: media Marca/AS, volatilidad/CV, tarjetas históricas.
   Son ruido.
