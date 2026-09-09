# Asistente de draft con Claude — diseño (NO implementado)

> Estado: **propuesta**. Nada de esto existe todavía en el repo.
> Escrito 2026-09-09, a 4 días del draft de la temporada 12.
> Decisión pendiente del admin.

Idea: un panel de chat dentro del draft en vivo (`/drafts/live/[draftId]`), visible
solo para el admin, que responda preguntas sobre **los datos que ya calcula la app**
mientras se está fichando.

---

## 1. Lo primero: no se puede "enlazar la cuenta de Claude.ai"

No existe un flujo OAuth que permita a una app self-hosted consumir una suscripción
de Claude.ai (Pro/Max). Esa suscripción cubre claude.ai y Claude Code, no una app propia.

Lo que sí funciona es una **API key de `console.anthropic.com`**, que se factura aparte
por tokens consumidos. Es una cuenta distinta de la suscripción, con su propio saldo y
sus propios límites de gasto.

---

## 2. Arquitectura

```
Navegador (admin en /drafts/live/[draftId])
   │  POST /api/draft/assistant   { pregunta, historial }
   ▼
FastAPI  ── require_perm(Perm.DRAFT) ───────────┐
   │  arma el contexto desde la BD:             │  la API key
   │    · tablero (DraftValueService)           │  nunca sale
   │    · picks actuales del draft              │  de aquí
   │    · plantilla del participante en turno   │
   ▼                                            │
Anthropic API (claude-opus-5) ──────────────────┘
   │  respuesta (streaming)
   ▼
Panel de chat en el draft en vivo
```

El frontend **nunca** habla con Anthropic. Siempre pasa por el backend. Eso es lo que
mantiene la key a salvo y permite controlar exactamente qué datos salen.

### Ficheros que habría que crear

| Ruta | Qué hace |
|---|---|
| `backend/src/features/draft_assistant/service.py` | Cliente `AsyncAnthropic`, construcción del prompt, streaming |
| `backend/src/features/draft_assistant/router.py` | `POST /draft/assistant`, gate `Perm.DRAFT` |
| `backend/src/features/draft_assistant/context.py` | Serializa tablero + picks + plantilla a texto compacto |
| `frontend/src/components/drafts/assistant-panel.tsx` | Panel de chat (colapsable, no roba sitio a las sugerencias) |

Reusa `DraftValueService` tal cual — el contexto **no** recalcula nada, solo formatea
lo que el tablero ya expone.

---

## 3. Seguridad de la API key

- Se crea en `console.anthropic.com` y va a `/opt/vpv/backend/.env`:
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  ```
- El SDK la lee sola: `anthropic.AsyncAnthropic()` sin argumentos. **No hardcodear.**
- **Nunca** como `NEXT_PUBLIC_*` — eso se empaqueta en el JS del navegador y sería pública.
- El `.env` ya está fuera de git, así que no hay riesgo de commitearla.
- Ponerle un **límite de gasto mensual** en la consola de Anthropic (el gasto esperado
  es de pocos dólares; el límite es contra un bug en bucle, no contra el uso normal).
- El endpoint queda tras `Perm.DRAFT` / `is_admin`, igual que el resto de admin.
  Conviene además un **rate limit por usuario** (p.ej. 30 preguntas/hora) — sin él, un
  bug de React que reenvíe en bucle sí puede costar dinero.

---

## 4. Qué contexto se envía

La clave es separar lo **estable** (se cachea, ~90% más barato en lecturas siguientes)
de lo **volátil** (cambia con cada pick, invalida la caché):

```python
response = await client.messages.create(
    model="claude-opus-5",
    max_tokens=2000,
    # ESTABLE → cacheado: reglas de la liga, puntuación, formaciones,
    # qué significa cada columna, y cómo debe comportarse.
    system=[{
        "type": "text",
        "text": REGLAS_VPV,
        "cache_control": {"type": "ephemeral"},
    }],
    # VOLÁTIL → en el mensaje: snapshot del tablero en este instante.
    messages=[
        *historial,
        {"role": "user", "content": f"{snapshot_tablero}\n\nPregunta: {pregunta}"},
    ],
)
```

`REGLAS_VPV` es texto fijo: puntuación, límite de 26 jugadores, formaciones válidas,
draft serpiente, y la definición de cada métrica (Prio, Base, VORP, Salto, Tier, Disp,
Fiab, DefEq) con su interpretación.

`snapshot_tablero` sería:
- los ~150 mejores **disponibles** con sus columnas (Prio, VORP, Tier, Disp, tags, banderas),
- los picks hechos hasta ahora,
- la plantilla actual del participante en turno vs. su objetivo (2/8/7/6).

### Qué datos salen del servidor

Nombres de jugadores, estadísticas de La Liga y el estado del draft. Todo eso es
información deportiva pública o derivada de ella.

**Recomendación**: mandar a los participantes como `Participante 3` en vez de sus
nombres reales. No aporta nada al razonamiento y evita enviar datos de terceros a
un servicio externo. La opción de "no entrenar con datos de API" es el
comportamiento por defecto de la API de Anthropic, pero el principio de mandar lo
mínimo se aplica igual.

### Verificar que la caché funciona

```python
print(response.usage.cache_read_input_tokens)   # debería ser >0 a partir de la 2ª pregunta
print(response.usage.cache_creation_input_tokens)
```

Si `cache_read_input_tokens` sale siempre 0, hay algo que varía en el prefijo
(una fecha, un UUID, un `json.dumps()` sin ordenar) y se está pagando todo a precio completo.

---

## 5. El punto crítico del diseño

El prompt de sistema debe decir **explícitamente**:

> El orden de fichaje ya está calculado y validado con backtest sobre 7 temporadas
> reales. No lo recalcules ni propongas un ranking propio. Tu trabajo es explicar y
> contrastar lo que ya está en el tablero.

Su trabajo es ser **una interfaz a los datos**, no una segunda opinión:

- **Explicar**: "¿por qué este está por encima de aquel?" → lee Prio/VORP/tags y lo traduce.
- **Comparar**: "de estos 3 disponibles, ¿cuál encaja mejor?" → cruza con la plantilla actual.
- **Avisar**: "llevas 4 del Betis", "vas corto de delanteros", "el Salto en MED es enorme,
  cógelo ya o pierdes 40 puntos de proyección".

Sin ese límite el modelo empezaría a opinar sobre jugadores de La Liga con conocimiento
desactualizado (su corte de entrenamiento no incluye el mercado de este año) y **peor
que el modelo propio**, que está medido: ρ 0.464 sobre 7 temporadas. Sería cambiar algo
validado por una intuición.

---

## 6. Coste

Con `claude-opus-5` ($5 entrada / $25 salida por millón de tokens):

| Concepto | Tokens | Coste |
|---|---|---|
| Reglas cacheadas (se escriben 1 vez) | ~5.000 | $0,03 |
| Por pregunta: snapshot + historial | ~7.000 | ~$0,01 |
| Por pregunta: respuesta | ~600 | ~$0,015 |
| **Por pregunta** | | **~$0,03** |
| **Sesión de draft completa (~100 preguntas)** | | **~$3** |

Irrelevante frente al valor. El riesgo de coste no es el uso normal, es un bucle
accidental — de ahí el rate limit y el límite de gasto en la consola.

Si se quisiera abaratar más, `claude-sonnet-5` ($2/$10) haría este trabajo
perfectamente, porque la parte difícil (el ranking) ya está resuelta en el backend.

---

## 7. Esfuerzo

| Pieza | Esfuerzo |
|---|---|
| `anthropic` en `requirements.txt` + key en `.env` | trivial |
| `draft_assistant/` (servicio + router + gate `Perm.DRAFT`) | ~medio día |
| Constructor del contexto (reusa `DraftValueService` y los picks) | ~medio día |
| Panel de chat con streaming (si no, parece colgado 10s) | ~medio día |
| Rate limit por usuario + tests | ~medio día |

Unos **2 días** para algo sólido.

---

## 8. Recomendación de calendario

**Después del draft de la temporada 12, no antes.** A 4 días del draft, meter una
dependencia externa nueva y una UI sin rodaje es más riesgo que beneficio comparado
con el prep operativo pendiente (tags rellenados, notas Marca/AS de J1-J3, ensayo de
draft real).

Si se decide seguir adelante, el primer paso —y el único que hay que hacer a mano— es
**crear la API key con límite de gasto** en `console.anthropic.com`. El resto es código.

---

## Referencias

- Modelo de draft y backtest: `docs/DRAFT_SCORECARD.md`, `docs/DRAFT_IMPROVEMENTS.md`
- Permisos: `backend/src/shared/permissions.py` (`Perm.DRAFT = 8`)
- Tablero: `backend/src/features/stats/service_draft.py`
- Draft en vivo: `frontend/src/app/drafts/live/[draftId]/page.tsx`
