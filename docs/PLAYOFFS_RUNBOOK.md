# Playoffs — Runbook operativo

Guía paso a paso para gestionar un playoff en producción.
- Reglas y estado: [PLAYOFFS_DESIGN.md](PLAYOFFS_DESIGN.md).
- Endpoints: [PLAYOFFS_API.md](PLAYOFFS_API.md).
- Añadir formatos: [PLAYOFFS_DEV_GUIDE.md](PLAYOFFS_DEV_GUIDE.md).

---

## Qué formato usar

| Competición | Formato | Jornadas |
|---|---|---|
| **Liga 2026-27** (Apertura y Clausura, 11 participantes) | `liga_berger_ko8_bo3` | 11 de liga + 5 de KO = 16 por playoff |
| Mundial / torneo (13 participantes) | `balanced_ko4` | 6 de liga + 2 de KO |
| Liga con final de una jornada (temporadas anteriores) | `liga_berger_ko8` | N de liga + 3 de KO |

**Prerequisitos:**
- Backend y frontend desplegados.
- La temporada con sus participantes **activos** y todas las jornadas del rango creadas en BD.
- Participantes que ya no juegan en `is_active=false`: cuentan para el nº de jornadas.

---

## A. Liga 2026-27: Apertura y Clausura

**Calendario:**

| Playoff | Liga | Cuartos | Semis | Final (al mejor de 3) |
|---|---|---|---|---|
| Apertura | J6–J16 | J17 | J18 | J19, J20, J21 |
| Clausura | J22–J32 | J33 | J34 | J35, J36, J37 |

La J38 queda libre.

### A.1 Crear los dos playoffs (una vez por temporada)

`/admin/temporadas` → temporada 2026-2027 → tarjetas **Playoff Apertura** y **Playoff Clausura**.

**Apertura:**
1. Formato «Liga todos contra todos + KO top-8, final al mejor de 3». Ya sale por defecto.
2. Pulsa **Crear Playoff**.
3. Comprueba los valores que propone la tarjeta:
   - **Jornada inicio: 6**;
   - **Jornadas KO: 17,18,19,20,21**;
   - el texto «Fase regular: J6 – J16».
4. Pulsa **Generar calendario**.

**Clausura:**
1. El mismo formato → **Crear Playoff**.
2. La tarjeta propone **inicio 22** y **KO 33,34,35,36,37**, con «Fase regular: J22 – J32».
3. Pulsa **Generar calendario**.

Si la tarjeta propone otros números (13 jornadas, por ejemplo), no generes: revisa los participantes activos de la temporada.

**Por curl:**

```bash
TOKEN="<jwt admin>"; SEASON_ID=12; API=https://new.ligavpv.com/api/competitions

APERTURA=$(curl -sf -X POST "$API/admin/season/$SEASON_ID" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format_id":"liga_berger_ko8_bo3","name":"Apertura"}' | jq -r .id)
curl -sf -X POST "$API/admin/$APERTURA/start-regular" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"matchday_start":6,"matchday_end":16,"planned_ko_matchday_numbers":[17,18,19,20,21]}'
# {"matchups_inserted":55}

CLAUSURA=$(curl -sf -X POST "$API/admin/season/$SEASON_ID" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format_id":"liga_berger_ko8_bo3","name":"Clausura"}' | jq -r .id)
curl -sf -X POST "$API/admin/$CLAUSURA/start-regular" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"matchday_start":22,"matchday_end":32,"planned_ko_matchday_numbers":[33,34,35,36,37]}'
```

**Qué pasa al generar:**
- Se sortea el calendario: todos contra todos, 5 cruces por jornada, y cada participante descansa una vez.
- Las jornadas del rango **ya puntuadas se resuelven en el momento**. Si creas la Apertura con la J6 cerrada, sus cruces salen con resultado.
- Las jornadas KO quedan planificadas y **las eliminatorias arrancan solas** al resolverse el último cruce de liga.

### A.2 Comprobar el calendario

En `/playoffs`, con el selector Apertura | Clausura, pestaña **Calendario**: 11 jornadas con 5 cruces cada una. O en SQL:

```sql
-- 5 cruces por jornada, 55 en total
SELECT round_number, COUNT(*) FROM competition_matchups
WHERE competition_id = <ID> AND phase = 'regular'
GROUP BY round_number ORDER BY round_number;

-- Cada participante juega 10 cruces (y por tanto descansa 1)
SELECT pid, COUNT(*) FROM (
  SELECT participant_a_id AS pid FROM competition_matchups WHERE competition_id = <ID> AND phase = 'regular'
  UNION ALL
  SELECT participant_b_id FROM competition_matchups WHERE competition_id = <ID> AND phase = 'regular'
) s GROUP BY pid ORDER BY pid;
```

### A.3 La liga avanza sola

Cada vez que se agrega una jornada (scraping o cierre), cada cruce de esa jornada toma los `participant_matchday_scores.total_points` de los dos participantes:
- **Victoria:** 3 puntos.
- **Empate:** 1 punto cada uno.
- **Descanso:** 0 puntos, cuenta como descanso.

**Clasificación, a igualdad de puntos:**
1. **Enfrentamiento directo.** Entre dos, su cruce. Entre tres o más, una minitabla solo con sus cruces, a 3 la victoria y 1 el empate.
2. **Diferencia** (puntos a favor menos en contra). Es lo que decide si empataron su cruce.

Si aun así siguen igualados, comparten puesto.

### A.4 Eliminatorias y final

- **Cuartos (J17 / J33):** 1-8, 4-5, 2-7 y 3-6, con los participantes ya puestos.
- **Semis (J18 / J34):** ganador 1-8 contra ganador 4-5, y ganador 2-7 contra ganador 3-6.
- **Empate en cuartos o semis:** pasa el mejor clasificado de la liga.
- **Final (J19–J21 / J35–J37):**
  - Tres cruces entre los dos finalistas; gana quien gane dos jornadas.
  - Si alguien gana las dos primeras, **la tercera no se disputa**. Se juega igual en VPV, pero no cuenta, y la web la marca «No se disputa».
  - Una jornada empatada la gana quien tenga **mejor diferencia en las otras dos jornadas de la final**. Por eso un empate siempre lleva la final a la tercera jornada.
  - Si también hay igualdad ahí, gana el mejor clasificado de la liga.
- **Cierre:** en cuanto hay campeón, el playoff pasa a `completed`, sea tras la 2.ª jornada o tras la 3.ª. `/playoffs` muestra la serie y el campeón.

---

## B. Mundial / torneo (`balanced_ko4`)

1. Tarjeta **Playoffs** (temporadas `tournament`), formato `balanced_ko4` → **Crear Playoff**.
2. **Jornada inicio**: el fin se calcula solo, 6 jornadas. **Jornadas KO**: se proponen `inicio+6, inicio+7`.
3. **Generar calendario** crea 26 cruces con distribución 5, 5, 5, 5, 3, 3; cada participante juega 4.
4. Al resolverse la última jornada de liga arrancan solas las semis (1-4 y 2-3, con participantes) y la final, con alimentadores.
5. **Empates:**
   - en la clasificación, puntos → diferencia (acordado con Oscar, porque no es un todos contra todos);
   - en semis y final, el mejor clasificado.

Por curl, igual que en A.1 con `{"format_id":"balanced_ko4"}` (sin `name`), `matchday_start`/`matchday_end` de 6 jornadas y 2 jornadas KO.

---

## Operaciones comunes

### Forzar el recálculo de una jornada

Tras cambiar `matches.counts` o cualquier ajuste retroactivo, reagrega la jornada. Reagregar recalcula las puntuaciones y, con ellas, los cruces:

```bash
cd /opt/vpv/backend
sudo -u vpv .venv/bin/python -m src.features.scraping.cli aggregate-matchday <season_id> <jornada>
```

Si también hay que volver a bajar las estadísticas, usa `scrape-matchday <season_id> <jornada>`.

### Arrancar las eliminatorias a mano

Solo si se generó el calendario sin jornadas KO planificadas. En la tarjeta: «Iniciar KO manualmente» con las jornadas separadas por comas (`17,18,19,20,21` en la Apertura). Por curl:

```bash
curl -sf -X POST "$API/admin/<ID>/start-ko" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"ko_matchday_numbers":[17,18,19,20,21]}'
```

---

## Cosas que pueden ir mal

### «El formato … requiere N jornadas para M participantes, recibidas K»

- **El rango no mide lo que pide el formato.** En la Liga 2026-27 son 11 jornadas.
- **La tarjeta calculó mal las jornadas:** el nº de participantes activos no es el esperado.

### «Empate sin desempate dentro del top-8 del playoff» (o «top-4» en el Mundial)

**Qué significa:** dos o más participantes siguen igualados tras todos los desempates del formato, y el empate afecta a quién entra (8.º y 9.º) o al puesto dentro del cuadro. El KO no arranca: cualquier orden sería arbitrario.
- En la Liga, los desempates son puntos, directo y diferencia.
- En el Mundial, puntos y diferencia.

**Cómo verlo:** `GET /api/competitions/<ID>/standings`, o la pestaña Clasificación. Los empatados comparten `rank`.

**Qué hacer:** hoy no hay un mecanismo para forzar el orden.
1. Acordad cómo resolverlo.
2. Pide que se implemente un «orden forzado» en `competitions.config`.
3. Mientras tanto, el arranque automático queda en el log (`Auto-start KO failed for competition N`) y reintenta en cada recálculo.

### «Quedan N cruces de fase regular sin resolver»

Algún cruce de liga no tiene marcador porque falta agregar su jornada:

```sql
SELECT round_number, matchday_id, participant_a_id, participant_b_id
FROM competition_matchups
WHERE competition_id = <ID> AND phase = 'regular'
  AND score_a IS NULL AND participant_b_id IS NOT NULL;
```

Reagrega esa jornada (ver «Forzar el recálculo»).

### Repetir el sorteo, antes de que empiece el KO

```sql
DELETE FROM competition_matchups WHERE competition_id = <ID>;
UPDATE competitions
SET status = 'pending',
    config = config - 'seed' - 'matchday_range_regular' - 'planned_ko_matchday_numbers'
WHERE id = <ID>;
```

Después vuelve a pulsar **Generar calendario**, o llama a `start-regular`. Hay que borrar también `planned_ko_matchday_numbers`: si no, se quedarían las jornadas KO antiguas cuando se genera sin ellas.

### Borrar el playoff entero

```sql
DELETE FROM competition_matchups WHERE competition_id = <ID>;
DELETE FROM competitions WHERE id = <ID>;
```

Vuelve a **Crear Playoff**. Crear es idempotente por nombre: con el playoff existente, devuelve el mismo en vez de crear otro.

### Formato equivocado

- **En `pending`:** `DELETE FROM competitions WHERE id = <ID> AND status = 'pending';` y créalo de nuevo.
- **Con el calendario generado:** «Borrar el playoff entero» y créalo con el formato correcto. El formato vive en `config.format_id`; no lo cambies a mano con cruces ya generados, porque el nº de jornadas KO no coincide entre formatos.

---

## Verificación de punta a punta

```sql
-- Estado y configuración
SELECT id, name, status, config->>'format_id', config->'matchday_range_regular',
       config->'planned_ko_matchday_numbers'
FROM competitions WHERE season_id = <SEASON>;

-- Cruces por fase y ronda (Liga: 11 rondas de 5; KO: 4 cuartos, 2 semis, 3 de final)
SELECT phase, round_label, round_number, COUNT(*)
FROM competition_matchups WHERE competition_id = <ID>
GROUP BY phase, round_label, round_number ORDER BY round_number;

-- Resultados de una jornada tras agregarla
SELECT round_number, score_a, score_b, winner_participant_id
FROM competition_matchups
WHERE competition_id = <ID>
  AND matchday_id = (SELECT id FROM matchdays WHERE season_id = <SEASON> AND number = <J>);
```

**La final** se comprueba mejor en `GET /api/competitions/<ID>/matchups`, en el campo `final_series`: jornadas ganadas, resultado de cada jornada y campeón. Una jornada de final empatada tiene `winner_participant_id = NULL` en su fila; quién la gana lo dice la serie.
