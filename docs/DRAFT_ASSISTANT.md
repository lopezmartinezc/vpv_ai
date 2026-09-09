# Asistente de draft — chat sobre el tablero en vivo

> Estado: **implementado**, desactivado por defecto (`ASSISTANT_ENABLED=false`).
> Solo admin. Funciona con **OpenAI (GPT)** por defecto o **Anthropic (Claude)**,
> elegible desde el propio chat.

Panel de chat dentro del draft en vivo (`/drafts/live/[draftId]`) que tiene como
base de conocimiento las estadísticas que ya calcula la app y **consulta la BD en
tiempo real** mientras se ficha.

---

## 1. Antes de nada: no se puede "enlazar la cuenta de Claude.ai"

No existe un flujo OAuth que permita a una app self-hosted consumir una
suscripción de Claude.ai (Pro/Max) ni de ChatGPT Plus. Esas suscripciones cubren
sus propias webs, no una app propia. Hace falta una **API key** de
`console.anthropic.com` o de `platform.openai.com`, facturada aparte por tokens.

---

## 2. Cómo activarlo

```bash
# /opt/vpv/backend/.env
ASSISTANT_ENABLED=true
ASSISTANT_PROVIDER=openai             # o "anthropic"
ANTHROPIC_API_KEY=sk-ant-...          # solo la del proveedor que uses
OPENAI_API_KEY=
ASSISTANT_ANTHROPIC_MODEL=claude-opus-5
ASSISTANT_OPENAI_MODEL=gpt-5
ASSISTANT_ANONYMIZE_PARTICIPANTS=true
```

Luego `pip install -e .` (hay dos dependencias nuevas) y reiniciar el backend.
Cambiar de proveedor es cambiar `ASSISTANT_PROVIDER` y reiniciar: las
herramientas, el prompt y la UI son los mismos.

**Antes de la primera pregunta**: pon un límite de gasto mensual en la consola
del proveedor. Es contra un bug en bucle, no contra el uso normal.

---

## 3. Arquitectura: tool use, no snapshot

El asistente no recibe un volcado del tablero. Recibe **herramientas** y consulta
solo lo que necesita:

```
Navegador (admin en /drafts/live/[draftId])
   │  POST /api/draft-assistant/{season_id}/{phase}/ask
   ▼
FastAPI  ── Depends(get_current_admin) ────────────────────────┐
   │                                                           │
   │  bucle de herramientas (mismo en ambos proveedores)       │
   │    modelo ──"buscar_jugadores(pos=DEL, disponibles)"──▶    │  las API keys
   │    modelo ◀──── filas reales del tablero ────────────      │  nunca salen
   │    modelo ──"estado_draft()"──────────────────────────▶    │  de aquí
   │    modelo ◀──── picks hechos, turno actual ──────────      │
   │    modelo ──── respuesta final ───────────────────────▶    │
   ▼                                                           │
Herramientas → DraftValueService / DraftService → PostgreSQL ───┘
```

Ventajas frente a meter el tablero en el prompt: siempre fresco, no se pagan
7.000 tokens de tablero en preguntas que necesitan tres filas, y no hay que
adivinar por adelantado qué datos incluir.

Las herramientas llaman a **los servicios que ya usa la UI**, no a SQL nuevo, así
que el chat y el tablero no pueden discrepar.

### Ficheros

| Ruta | Qué hace |
|---|---|
| `backend/src/features/draft_assistant/tools.py` | `ToolSpec`, adaptadores por proveedor, `run_tool` (la frontera de seguridad) |
| `backend/src/features/draft_assistant/board_tools.py` | Las 9 herramientas sobre los servicios existentes + caché del tablero |
| `backend/src/features/draft_assistant/turn_math.py` | Proyección del orden serpiente (próximos turnos, espera hasta el siguiente) |
| `backend/src/features/draft_assistant/providers/base.py` | Contrato común (`AssistantProvider`, `ChatMessage`, `AssistantReply`) |
| `backend/src/features/draft_assistant/providers/anthropic_provider.py` | Messages API + bucle manual |
| `backend/src/features/draft_assistant/providers/openai_provider.py` | Responses API + bucle manual |
| `backend/src/features/draft_assistant/service.py` | Prompt de sistema, elección de proveedor, un turno |
| `backend/src/features/draft_assistant/router.py` | `POST .../ask`, gate admin, rate limit |
| `frontend/src/components/draft/assistant-panel.tsx` | Panel colapsable en el draft en vivo |

### Por qué bucle manual y no `tool_runner`

El SDK de Anthropic trae `client.beta.messages.tool_runner`, que gestiona el
bucle solo. No se usa por dos razones: es beta, y exige declarar las herramientas
con su decorador `@beta_tool` — lo que obligaría a escribirlas dos veces, una por
proveedor. El bucle son ~30 líneas y queda simétrico con el de OpenAI, que es
justo el objetivo de la abstracción.

### Diferencias entre las dos APIs (las que importan al bucle)

| | Anthropic (Messages) | OpenAI (Responses) |
|---|---|---|
| Prompt de sistema | `system=[...]`, cacheable | `instructions="..."` |
| Forma de la herramienta | `{name, description, input_schema}` | `{type:"function", name, description, parameters}` |
| Llamada del modelo | bloque `tool_use` con `.id` | item `function_call` con `.call_id` |
| Devolver resultado | `{type:"tool_result", tool_use_id, content}` | `{type:"function_call_output", call_id, output}` |
| Eco del turno | `{"role":"assistant","content": blocks}` | los items de `response.output` |

La de OpenAI es la **Responses API** del SDK 3.x, no la vieja chat-completions:
la forma de la herramienta es plana, no anidada bajo `"function"`.

### Velocidad

El tablero agrega todas las filas de `player_stats` de las últimas temporadas
(~400 ms de SQL medidos, más la proyección en Python). Nada de eso cambia
mientras corre un draft, así que se **cachea 60 s** por temporada
(`BOARD_TTL_SECONDS`) y las preguntas seguidas no lo recalculan.

Lo que **no** se cachea es quién está fichado: se lee siempre de los picks en
vivo (`ctx.picked_ids()`), nunca del `is_drafted` que viaja con el tablero
cacheado. Si se confiara en ese flag, el asistente seguiría recomendando a un
jugador que acaban de coger — el peor fallo posible en mitad de un draft. Hay un
test que lo fija.

La caducidad que sí existe: un tag o un valor manual editados en el tablero
tardan hasta 60 s en llegar al asistente.

### Progreso en vivo

`POST .../ask/stream` responde por **Server-Sent Events**: un evento `tool` por
cada consulta según ocurre, y un único `done` con la respuesta completa (o
`error`). El panel muestra *"Consultando buscar_jugadores…"* mientras trabaja,
que es donde se va casi todo el tiempo de una pregunta. `/ask` sigue existiendo
con la respuesta JSON de golpe.

El frontend lo lee con `fetch` a mano (`lib/sse.ts`), no con `EventSource`, que
no puede mandar cuerpo ni cabecera `Authorization`. La respuesta lleva
`X-Accel-Buffering: no` para que Nginx no la retenga entera hasta el final.

### Limitación conocida del historial

La conversación se guarda como texto plano usuario/asistente. Las llamadas a
herramientas viven y mueren dentro de un turno: el modelo ve sus resultados
mientras responde, pero en turnos posteriores solo ve su propio resumen en prosa,
no las filas crudas. Es lo que permite que el historial sea portable entre
proveedores (los dos formatos de tráfico de herramientas no se parecen en nada).
A cambio, si necesita un dato de hace dos preguntas, vuelve a consultarlo — que
cuesta una vuelta más pero nunca da un dato viejo.

---

## 4. Las herramientas

| Herramienta | Devuelve |
|---|---|
| `buscar_jugadores(posicion?, equipo?, solo_disponibles?, orden?, limite?)` | Filas del tablero: Prio, Base, VORP, Salto, Tier, Disp, tags, banderas |
| `detalle_jugador(nombre)` | Ficha completa: métricas, histórico, Marca/AS, flags, valor manual y nota |
| `estado_draft()` | Resumen: picks hechos, siguiente pick, a quién le toca, últimos 10, y **quién está preguntando** |
| `picks_realizados(participante?, posicion?, equipo?, ronda?, limite?)` | El histórico **completo** de picks, filtrable |
| `proximos_turnos(cuantos?)` | Orden de los próximos picks y **cuántos picks espera cada uno** hasta su siguiente turno |
| `plantilla(participante?)` | Reparto por posición vs. plazas de titular. **Sin argumento, la de quien pregunta** |
| `plantillas_todas()` | El reparto de **todos** los participantes de un vistazo, señalando a quién le faltan titulares |
| `escasez_posicional()` | Por posición y entre los disponibles AHORA: mejor, caída al 3º, cuántos superan el reemplazo |
| `escasez_historica()` | La tabla de 8 temporadas de la sección 7 (dato fijo) |

Preguntas como *"con el pick 5, ¿me interesa un portero top o espero?"* se
responden encadenando `proximos_turnos` → `escasez_posicional` →
`buscar_jugadores(POR)` → `escasez_historica`, con números reales en cada paso.

### Sabe con quién habla

El `user_id` sale del JWT y nunca del modelo: el asistente decide *qué* preguntar,
nunca *en nombre de quién*. Con eso, `estado_draft` dice quién pregunta y si es su
turno, y `plantilla()` sin argumento devuelve **la suya**.

Antes devolvía la del turno actual, así que "¿de qué posición voy corto?" respondía
sobre otra persona siempre que no fuera tu turno — las mismas palabras, otra
plantilla, y nada en pantalla que lo indicara. Si quien pregunta solo administra y
no juega, se dice y se cae a la del turno.

### Por qué `proximos_turnos` es la clave

"¿Puedo esperar a este jugador?" no depende del jugador, depende de **cuántos
picks pasan hasta que vuelves a elegir**. En serpiente esa distancia es muy
desigual: quien está en el giro elige **dos veces seguidas**, quien está arriba
del orden espera **casi dos rondas enteras**. Sin ese número, el consejo de
esperar puede ser justo el contrario del correcto — por eso el prompt obliga a
consultarlo antes de responder nada sobre timing.

La matemática vive en `turn_math.py` y se apoya en el
`_get_participant_for_pick` del servicio de drafts, así que la regla de la
serpiente está definida en un solo sitio y el asistente no puede proyectar un
orden distinto del que muestra la pantalla.

---

## 5. Seguridad

### Regla dura: no existe una herramienta `ejecutar_sql`

Es la tentación obvia ("que consulte lo que quiera") y es un error. Los nombres
de jugadores y los tags vienen de scraping y de entrada manual, y acaban dentro
del prompt: SQL libre sería una superficie de inyección. Y un `SELECT` sin índice
bloquearía una tabla en mitad del draft. **El modelo elige qué preguntar, nunca
cómo.**

### `run_tool` es la frontera

Todo lo que manda el modelo llega ahí como entrada no fiable, así que:

- **Solo pasan los argumentos que declara el esquema.** Un `season_id` o
  `participant_id` inventado se descarta con un warning en el log, no llega al
  handler.
- **Los números se recortan a los límites del esquema.** Pedir 5.000 filas
  devuelve 50.
- **Un nombre de herramienta inexistente o un handler que peta** devuelven un
  string de error que el modelo puede leer, no una excepción que tumba la
  petición en mitad del draft.

### Los identificadores vienen del request

`season_id` y `phase` salen de la URL; el usuario, del JWT. Ninguna herramienta
los acepta como parámetro.

### Resto

- **API keys** solo en el `.env` del backend. **Nunca** `NEXT_PUBLIC_*` — eso se
  empaqueta en el JS del navegador y sería público. El `.env` ya está fuera de git.
- **Solo admin** (`Depends(get_current_admin)`). No es delegable por el bit
  `Perm.DRAFT`.
- **Sin límite de consultas.** Durante un draft se pregunta lo que haga falta, y
  un tope que salta a mitad de un pick es peor que el gasto que evita. La app no
  registra `SlowAPIMiddleware`, así que sin decorador la ruta queda realmente sin
  límite (los `default_limits` globales no se aplican a rutas sin decorar). Hay
  un test que lo fija, y otro que avisa si alguien añade el middleware.
- **Tope de vueltas de herramientas POR PREGUNTA** (`ASSISTANT_MAX_TOOL_ROUNDS`,
  por defecto 20): es lo único que queda, y no limita cuántas preguntas haces —
  evita que un modelo atascado en bucle sangre tokens en una sola. Estuvo en 8 y
  se quedaba corto: *"¿a quién cojo en este pick?"* encadena `estado_draft` →
  `proximos_turnos` → `plantilla` → `escasez_posicional` → `buscar_jugadores` en
  las 4 posiciones = 8 llamadas, y se cortaba justo antes de responder. Si vuelve
  a pasar, el mensaje dice qué llegó a consultar y se sube por `.env` sin desplegar.
- **Entrada acotada**: pregunta ≤ 4.000 caracteres, historial ≤ 80 mensajes. Es
  para que un cliente roto no mande un megabyte, no para racionar la conversación.
- **Límite de gasto** en la consola del proveedor. Es el sitio correcto para un
  límite de dinero: corta el gasto sin cortarte a ti a mitad de draft.

### Qué datos salen del servidor

Solo lo que devuelvan las herramientas: nombres de jugadores, estadísticas de La
Liga y estado del draft — información deportiva pública o derivada de ella. Los
participantes se envían como `Participante 3` salvo que pongas
`ASSISTANT_ANONYMIZE_PARTICIPANTS=false`.

---

## 6. El punto crítico del diseño

El prompt de sistema (`service.py::SYSTEM_PROMPT`) dice explícitamente:

> El orden de fichaje YA está calculado y validado con backtest sobre 7
> temporadas reales. NO lo recalcules, NO propongas un ranking propio y NO opines
> sobre jugadores desde tu conocimiento previo. Responde SIEMPRE consultando las
> herramientas.

Su trabajo es **explicar** (por qué un jugador está por encima de otro),
**comparar** (cuál encaja con la plantilla) y **avisar** (concentración de un
equipo, huecos, saltos grandes). No es dar una segunda opinión.

Sin ese límite, el modelo opinaría sobre jugadores de La Liga con conocimiento
desactualizado —su corte de entrenamiento no incluye el mercado de este año— y
**peor que el modelo propio**, que está medido: ρ 0.464 sobre 7 temporadas.

---

## 7. Escasez posicional histórica (fuente de `escasez_historica`)

Medido sobre 8 temporadas reales de la liga (puntos finales, `matchdays.counts` y
`matches.counts` respetados). Reemplazo = participantes × plazas de titular
(POR 1, DEF 4, MED 3, DEL 3).

| Pos | Excedente del 1º sobre el reemplazo | Coste de esperar al 3º | al 6º | Nivel de reemplazo |
|---|---|---|---|---|
| **DEL** | **193** | 70 | 105 | 134 |
| DEF | 118 | 28 | 49 | 135 |
| **POR** | **116** | **47** | **76** | 141 |
| MED | 97 | 25 | 44 | 156 |

1. **El mejor delantero vale ~77 puntos más de excedente que el mejor portero**, y
   gana en las 8 temporadas sin excepción. Con pick temprano, si queda un delantero
   top, es él.
2. **Portería es la SEGUNDA posición más escasa**, no la última: esperar del 1º al
   3º cuesta 47 puntos, frente a 28 en defensa y 25 en medio. La intuición de que
   "la portería puede esperar" es falsa.
3. Orden real de urgencia: **DEL >> POR > DEF ≈ MED**.
4. En 6 de 8 temporadas el portero más puntuado fue del Madrid, Barça o Atlético
   (Oblak ×3, Courtois ×2, ter Stegen ×1). Pero solo la mitad de los top-3 salieron
   de ahí — David Soria (Getafe) aparece 2 veces, y también Unai Simón, Remiro,
   Bono y Radu.

Caveats: son puntos reales (visión retrospectiva), así que la tabla mide la
**forma de la curva**, no el acierto al elegir. Los porteros son más predecibles
que los delanteros (juegan todo, sus puntos siguen a la defensa del equipo), lo
que juega ligeramente a su favor frente a esta tabla. Los totales de 2024-25 son
más bajos porque solo computaron 27 jornadas.

> **Gotcha**: el `pick_number` del histórico migrado **no es el orden real de
> draft** — está reconstruido por bloques de posición (los 11 primeros picks de
> 2024-25 son todos porteros). El MySQL antiguo no guardaba la secuencia. No se
> puede calcular ADP histórico de esta liga.

---

## 8. Coste

Con `claude-opus-5` ($5 entrada / $25 salida por millón). Una pregunta son 2-3
llamadas a la API (consulta, recibe, responde), y cada vuelta reenvía el historial:

| Concepto | Coste |
|---|---|
| Prompt de reglas + herramientas, cacheado (se escribe 1 vez) | $0,02 |
| Por pregunta: 2-3 vueltas con resultados de herramientas | ~$0,03 |
| Por pregunta: respuesta | ~$0,02 |
| **Por pregunta** | **~$0,05** |
| **Sesión de draft (~100 preguntas)** | **~$5** |

Verificar que la caché funciona con `response.usage.cache_read_input_tokens`: si
sale siempre 0, algo varía en el prefijo del prompt y se está pagando todo a
precio completo.

Con `claude-sonnet-5` ($2/$10) o el modelo equivalente de OpenAI bajaría a ~$2 la
sesión y haría este trabajo igual de bien: la parte difícil (el ranking) ya está
resuelta en el backend.

---

## 9. Pendiente

- **Streaming token a token** de la respuesta final. El progreso ya va en vivo
  (sección *Progreso en vivo*); lo que falta es que el texto final aparezca según
  se escribe. Con herramientas en el bucle ahorra poco y cuesta una ruta distinta
  por proveedor, así que se ha dejado para después.
- **Aritmética de serpiente en la UI.** El asistente ya la tiene
  (`proximos_turnos`), pero seguiría siendo útil como columna o aviso en el
  tablero, sin coste por token: *"si esperas al pick 18, en portería pierdes ~X"*.
- **Invalidar la caché al editar un tag**, en vez de esperar los 60 s.
- **Comparar proveedores.** El toggle existe; falta usarlo en un draft real y ver
  si uno responde mejor que el otro para este trabajo.

---

## Referencias

- Modelo de draft y backtest: `docs/DRAFT_SCORECARD.md`, `docs/DRAFT_IMPROVEMENTS.md`
- Permisos: `backend/src/shared/permissions.py`
- Tablero: `backend/src/features/stats/service_draft.py`
- Draft en vivo: `frontend/src/app/drafts/live/[draftId]/page.tsx`
