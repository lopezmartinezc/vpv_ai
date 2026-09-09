# Asistente de draft con Claude — diseño (NO implementado)

> Estado: **propuesta**. Nada de esto existe todavía en el repo.
> Escrito 2026-09-09. Revisado el mismo día: el diseño pasó de "snapshot en el
> prompt" a **tool use con acceso en vivo a la BD**, que es lo que se pidió.

Objetivo: un panel de chat dentro del draft en vivo (`/drafts/live/[draftId]`),
visible solo para el admin, que tenga como base de conocimiento **las estadísticas
que ya calcula la app** y pueda **consultar la BD en tiempo real** durante el draft.

---

## 1. Lo primero: no se puede "enlazar la cuenta de Claude.ai"

No existe un flujo OAuth que permita a una app self-hosted consumir una suscripción
de Claude.ai (Pro/Max). Esa suscripción cubre claude.ai y Claude Code, no una app propia.

Lo que sí funciona es una **API key de `console.anthropic.com`**, facturada aparte por
tokens consumidos, con su propio saldo y su propio límite de gasto.

---

## 2. Arquitectura: tool use, no snapshot

La primera versión de este documento proponía volcar el tablero entero en cada
pregunta. **Descartado.** Con acceso en vivo es mejor darle *herramientas* y que
consulte solo lo que necesita:

```
Navegador (admin en /drafts/live/[draftId])
   │  POST /api/draft/assistant   { pregunta, historial }
   ▼
FastAPI  ── require_perm(Perm.DRAFT) ──────────────────────────┐
   │                                                           │
   │  tool_runner: bucle automático                            │
   │    Claude ──"buscar_jugadores(pos=DEL, disponibles)"──▶    │  la API key
   │    Claude ◀──── filas reales del tablero ────────────      │  nunca sale
   │    Claude ──"estado_draft()"──────────────────────────▶    │  de aquí
   │    Claude ◀──── picks hechos, turno actual ──────────      │
   │    Claude ──── respuesta final ───────────────────────▶    │
   ▼                                                           │
Herramientas → DraftValueService / DraftService → PostgreSQL ───┘
```

Ventajas frente al snapshot:

- **Siempre fresco**: cada consulta ve el estado real del draft, no una foto del
  momento en que se abrió el chat.
- **Más barato**: no se pagan 7.000 tokens de tablero en preguntas que solo
  necesitan tres filas.
- **Escala a cualquier pregunta**: no hay que adivinar por adelantado qué datos
  meter en el contexto.

Las herramientas llaman a los **servicios que ya existen** (`DraftValueService`,
el servicio de drafts), no a SQL nuevo. Así el chat y la UI no pueden discrepar.

### Ficheros que habría que crear

| Ruta | Qué hace |
|---|---|
| `backend/src/features/draft_assistant/tools.py` | Las herramientas (`@beta_async_tool`) |
| `backend/src/features/draft_assistant/service.py` | `tool_runner`, prompt de sistema, streaming |
| `backend/src/features/draft_assistant/router.py` | `POST /draft/assistant`, gate `Perm.DRAFT` |
| `frontend/src/components/drafts/assistant-panel.tsx` | Panel de chat colapsable |

---

## 3. Las herramientas

```python
from anthropic import beta_async_tool

@beta_async_tool
async def buscar_jugadores(
    posicion: str | None = None,
    equipo: str | None = None,
    solo_disponibles: bool = True,
    orden: str = "prioridad",
    limite: int = 20,
) -> str:
    """Busca jugadores en el tablero de draft de la temporada en curso.

    Args:
        posicion: POR, DEF, MED o DEL. Omitir para todas.
        equipo: nombre del equipo de La Liga. Omitir para todos.
        solo_disponibles: si True, excluye los ya fichados en este draft.
        orden: "prioridad" o "vorp".
        limite: cuántos devolver, máximo 50.
    """
```

| Herramienta | Devuelve |
|---|---|
| `buscar_jugadores(...)` | Filas del tablero: Prio, Base, VORP, Salto, Tier, Disp, tags, banderas |
| `detalle_jugador(nombre)` | Ficha completa + rendimiento de esta temporada (goles, min, Marca/AS, forma) |
| `estado_draft()` | Picks hechos, ronda, turno actual, quién queda por elegir |
| `plantilla(participante)` | Plantilla actual vs. objetivo 2/8/7/6, con los huecos |
| `escasez_posicional()` | VORP sobre reemplazo y Salto agregados por posición, ahora mismo |
| `escasez_historica()` | La tabla de 8 temporadas de la sección 7 (dato fijo, no consulta) |

Con eso, preguntas como *"con el pick 5, ¿me interesa un portero top o espero?"* se
responden encadenando `estado_draft` → `escasez_posicional` → `buscar_jugadores(POR)`
→ `escasez_historica`, con números reales en cada paso.

### El bucle

```python
runner = client.beta.messages.tool_runner(
    model="claude-opus-5",
    max_tokens=4000,
    tools=[buscar_jugadores, detalle_jugador, estado_draft, plantilla,
           escasez_posicional, escasez_historica],
    system=[{"type": "text", "text": REGLAS_VPV,
             "cache_control": {"type": "ephemeral"}}],
    messages=historial + [{"role": "user", "content": pregunta}],
)
async for message in runner:
    ...  # emitir por SSE al frontend
```

El SDK gestiona el bucle: llama a la herramienta, le pasa el resultado a Claude y
repite hasta que no haya más llamadas.

---

## 4. Seguridad

### Regla dura: nunca una herramienta `ejecutar_sql`

Es la tentación obvia ("que consulte lo que quiera") y es un error. Un modelo con SQL
libre sobre la BD de producción es una superficie de inyección — los nombres de jugadores
y los tags vienen de scraping y de entrada manual, y acaban dentro del prompt — y además
un pie de fuego: un `DELETE` mal formado, o un `SELECT` sin índice que bloquea la tabla
en mitad del draft.

Herramientas **cerradas y tipadas** únicamente. El modelo elige *qué* preguntar, no *cómo*.

### Los identificadores vienen del request, no del modelo

`season_id`, `draft_id` y el `participant_id` del que consulta salen de la URL y del JWT.
Ninguna herramienta los acepta como parámetro. Si los aceptara, bastaría un tag malicioso
—o una alucinación— para leer datos de otra temporada u otro participante.

### Resto

- **API key** en `/opt/vpv/backend/.env` como `ANTHROPIC_API_KEY=sk-ant-...`. El SDK la
  lee sola con `AsyncAnthropic()`. **Nunca** `NEXT_PUBLIC_*` — eso se empaqueta en el JS
  del navegador y sería pública. El `.env` ya está fuera de git.
- **Usuario de BD de solo lectura** para las herramientas del asistente. Defensa en
  profundidad: aunque una herramienta tuviera un bug, no puede escribir.
- **Límites del lado servidor**: `limite` se capa a 50 aunque el modelo pida 5.000.
- **Rate limit por usuario** (p.ej. 30 preguntas/hora). Sin él, un bucle de React que
  reenvíe solo sí puede costar dinero.
- **Límite de gasto mensual** en la consola de Anthropic. Es contra un bug, no contra
  el uso normal.
- **Endpoint tras `Perm.DRAFT` / `is_admin`**, como el resto de admin.

### Qué datos salen del servidor

Solo lo que devuelvan las herramientas: nombres de jugadores, estadísticas de La Liga y
estado del draft — información deportiva pública o derivada de ella. Recomendación:
devolver a los participantes como `Participante 3` en vez de sus nombres reales. No
aporta nada al razonamiento y evita mandar datos de terceros a un servicio externo.

---

## 5. El punto crítico del diseño

El prompt de sistema debe decir **explícitamente**:

> El orden de fichaje ya está calculado y validado con backtest sobre 7 temporadas
> reales. No lo recalcules ni propongas un ranking propio. Responde SIEMPRE consultando
> las herramientas; nunca de memoria. Si una herramienta no da el dato, dilo.

Su trabajo es ser **una interfaz a los datos**, no una segunda opinión:

- **Explicar**: "¿por qué este está por encima de aquel?" → lee Prio/VORP/tags y traduce.
- **Comparar**: "de estos 3 disponibles, ¿cuál encaja mejor?" → cruza con la plantilla.
- **Avisar**: "llevas 4 del Betis", "vas corto de delanteros", "el Salto en MED es enorme".

Sin ese límite el modelo opinaría sobre jugadores de La Liga con conocimiento
desactualizado (su corte de entrenamiento no incluye el mercado de este año) y **peor
que el modelo propio**, que está medido: ρ 0.464 sobre 7 temporadas.

---

## 6. Coste

Con `claude-opus-5` ($5 entrada / $25 salida por millón de tokens). Con tool use, una
pregunta son 2-3 llamadas a la API (el modelo consulta, recibe, responde), y cada una
reenvía el historial:

| Concepto | Coste |
|---|---|
| Reglas + definición de herramientas, cacheadas (se escriben 1 vez) | $0,02 |
| Por pregunta: 2-3 vueltas con resultados de herramientas | ~$0,03 |
| Por pregunta: respuesta | ~$0,02 |
| **Por pregunta** | **~$0,05** |
| **Sesión de draft completa (~100 preguntas)** | **~$5** |

Algo más caro por pregunta que el snapshot, y merece la pena: los datos son los de
ese instante. Verificar que la caché funciona con `response.usage.cache_read_input_tokens`
— si sale siempre 0, algo varía en el prefijo (una fecha, un UUID, un `json.dumps()`
sin ordenar) y se está pagando todo a precio completo.

`claude-sonnet-5` ($2/$10) haría este trabajo perfectamente y costaría ~$2 la sesión:
la parte difícil (el ranking) ya está resuelta en el backend, aquí solo hay que leer
herramientas y redactar.

---

## 7. Escasez posicional histórica (dato para `escasez_historica`)

Medido sobre 8 temporadas reales de la liga (puntos finales, `matchdays.counts` y
`matches.counts` respetados). Reemplazo = participantes × plazas de titular
(POR 1, DEF 4, MED 3, DEL 3).

| Pos | Excedente del 1º sobre el reemplazo | Coste de esperar al 3º | al 6º | Nivel de reemplazo |
|---|---|---|---|---|
| **DEL** | **193** | 70 | 105 | 134 |
| DEF | 118 | 28 | 49 | 135 |
| **POR** | **116** | **47** | **76** | 141 |
| MED | 97 | 25 | 44 | 156 |

Conclusiones:

1. **El mejor delantero vale ~77 puntos más de excedente que el mejor portero**, y gana
   en las 8 temporadas sin excepción. Con un pick temprano, si queda un delantero top, es él.
2. **Portería es la SEGUNDA posición más escasa**, no la última: esperar del 1º al 3º
   cuesta 47 puntos, frente a 28 en defensa y 25 en medio. La intuición de que "la
   portería puede esperar" es falsa.
3. Orden real de urgencia: **DEL >> POR > DEF ≈ MED**.
4. En 6 de 8 temporadas el portero más puntuado fue del Madrid, Barça o Atlético
   (Oblak ×3, Courtois ×2, ter Stegen ×1). Pero solo la mitad de los top-3 salieron de
   ahí — David Soria (Getafe) aparece 2 veces, y también Unai Simón, Remiro, Bono y Radu.

Caveats: son puntos reales (visión retrospectiva), así que la tabla mide la **forma de
la curva**, no el acierto al elegir. Los porteros son más predecibles que los delanteros
(juegan todo, sus puntos siguen a la defensa del equipo), lo que juega ligeramente a su
favor frente a esta tabla. Los totales de 2024-25 son más bajos porque solo computaron
27 jornadas.

> **Nota**: el `pick_number` del histórico migrado **no es el orden real de draft** —
> está reconstruido por bloques de posición (los 11 primeros picks de 2024-25 son todos
> porteros). El MySQL antiguo no guardaba la secuencia. No se puede calcular ADP histórico.

---

## 8. Esfuerzo

| Pieza | Esfuerzo |
|---|---|
| `anthropic` en `requirements.txt` + key en `.env` + usuario BD de solo lectura | ~1h |
| `tools.py` — 6 herramientas sobre los servicios existentes | ~medio día |
| `service.py` + `router.py` — tool_runner, prompt, SSE, rate limit | ~medio día |
| Panel de chat con streaming (si no, parece colgado 10s) | ~medio día |
| Tests (herramientas con BD de test; el bucle mockeado) | ~medio día |

Unos **2 días** para algo sólido.

---

## 9. Recomendación de calendario

**Después del draft de la temporada 12, no antes.** A 4 días del draft, meter una
dependencia externa nueva y una UI sin rodaje es más riesgo que beneficio comparado
con el prep operativo pendiente (tags rellenados, notas Marca/AS de J1-J3, ensayo de
draft real).

Lo que sí cabe antes del draft y ataca el mismo problema es la **aritmética de
serpiente**: conocida tu posición de pick, la app sabe tus turnos (5 → 18 → 31…) y ya
tiene la columna Salto; cruzarlas da *"si esperas al pick 18, en portería pierdes ~X"*
sin dependencias nuevas ni coste por token.

Si se decide seguir adelante con el chat, el primer paso —y el único manual— es
**crear la API key con límite de gasto** en `console.anthropic.com`.

---

## Referencias

- Modelo de draft y backtest: `docs/DRAFT_SCORECARD.md`, `docs/DRAFT_IMPROVEMENTS.md`
- Permisos: `backend/src/shared/permissions.py` (`Perm.DRAFT = 8`)
- Tablero: `backend/src/features/stats/service_draft.py`
- Draft en vivo: `frontend/src/app/drafts/live/[draftId]/page.tsx`
