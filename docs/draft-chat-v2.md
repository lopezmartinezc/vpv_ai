# Chat del draft: experimento V2

## Activación
El selector **Actual / Experimental V2** aparece en el draft online para administradores.
Actual sigue siendo el predeterminado y conserva su componente e historial en memoria.
V2 se monta únicamente al abrir su pestaña. No se consultan ambos proveedores automáticamente.

Antes de usar V2, aplicar la migración desde backend con el entorno de destino revisado:
```sh
.venv/bin/alembic upgrade head
```
La implementación no aplica migraciones ni modifica picks existentes.

V2 reutiliza las credenciales y modelos predeterminados del asistente.
Configuración adicional (backend, prefijo independiente):
- `ASSISTANT_V2_ENABLED=false`: desactiva V2 sin afectar a Actual.
- `ASSISTANT_V2_OPENAI_MODELS='["modelo-permitido"]'` y
  `ASSISTANT_V2_ANTHROPIC_MODELS='["modelo-permitido"]'`: listas adicionales.
- `ASSISTANT_V2_TIMEOUT_SECONDS=150`, `ASSISTANT_V2_PROVIDER_TIMEOUT_SECONDS=90`,
  `ASSISTANT_V2_MAX_ROUNDS=20`,
  `ASSISTANT_V2_MAX_TOOL_CALLS=30`, `ASSISTANT_V2_MAX_OUTPUT_TOKENS=8000`.

  `MAX_OUTPUT_TOKENS` incluye los **tokens de razonamiento**, no solo el texto
  visible. Con gpt-5 el valor inicial de 2000 se agotaba pensando y la
  respuesta volvía truncada y vacía: "Análisis incompleto" sin una línea de
  texto. Si vuelve a pasar, el propio aviso en pantalla dice ahora qué límite
  se ha tocado.

  Los timeouts están dimensionados para un modelo de razonamiento: una sola
  llamada a gpt-5 con 8000 tokens de salida tarda 30-60 s. El total (150 s)
  queda por debajo del aborto del navegador (190 s) y del `proxy_read_timeout`
  de nginx para `/api` (300 s).

## Coste por ronda

En Anthropic el sistema, las herramientas y el último bloque de cada mensaje
van marcados con `cache_control: ephemeral`, como en el chat actual, de modo
que cada ronda reutiliza el prefijo de la anterior. OpenAI cachea prefijos
largos sin pedirlo.

`estado_draft` resume los picks (total, ronda actual, recuento por
participante y los 12 últimos) en vez de listarlos todos: la lista completa
vive en `plantillas`. Si el modelo vuelve a pedir `estado_draft` o
`evaluar_pick`, que ya recibió en el primer mensaje, obtiene "consulta
repetida" en lugar de otra copia.

  El presupuesto de rondas arranca donde acabó V1, no donde empezó: "¿a quién
  cojo en este pick?" encadena ocho o más llamadas a herramientas, V1 salió con
  ocho y producción respondió "me he quedado sin vueltas consultando datos".
  Fijado en `tests/test_budget.py`.

## Comportamiento
- Contexto visible: jugador abierto, comparación hasta tres, filtros, orden y plantilla objetivo.
- Snapshot consistente, propiedad real (también invierno), formaciones de BD y revalidación final.
- Las tarjetas numéricas provienen del servidor; la explicación generada **no es una validación
  automática de todas las afirmaciones del modelo**.
- Cambios en picks, métricas o tags invalidan tarjetas. La UI revisa cada 30 segundos mientras está activa.
- Herramientas de lectura: tablero, turnos, plantillas, evaluación, calendario y rendimiento observado.
  No noticias ni probabilidades inventadas de disponibilidad futura.
- Cancelación al cambiar de pestaña; bloqueo de consultas simultáneas por usuario/draft.
- Historial V2 privado persistido (últimos 40 intercambios), borrable desde V2.
  Se envía contexto necesario al proveedor; OpenAI usa `store:false`, lo que no equivale
  a garantizar ausencia absoluta de retención del proveedor.
- La selección de una tarjeta abre detalles; nunca realiza un pick.
- Para comparar, enviar manualmente la misma pregunta en cada versión. Hay coste por cada consulta.

## Comprobación local
```sh
cd backend
DEBUG=false .venv/bin/pytest src/features/draft_assistant_v2/tests --confcutdir=src/features/draft_assistant_v2/tests -q
.venv/bin/mypy src/features/draft_assistant_v2 --follow-imports=silent
.venv/bin/ruff check src/features/draft_assistant_v2
cd ../frontend
npx tsc --noEmit
npx vitest run src/features/draft-assistant-v2
```
No usar los fixtures globales antiguos contra una BD de trabajo: su estrategia de recreación
requiere revisión independiente. Las pruebas unitarias de V2 no llaman proveedores reales.
Pendiente de validación operativa: migración en entorno de pruebas, E2E con navegador,
y compatibilidad/calidad de cada modelo configurado con consultas reales.

## Resultado de pruebas de implementación
- 46 tests backend V2, incluido PostgreSQL desechable con Testcontainers.
- 90% de cobertura del código backend V2 (excluyendo tests).
- 81 tests de regresión del asistente original.
- 6 tests frontend V2: transporte, conservación del chat Actual y cancelación.
- TypeScript, mypy y lint V2 correctos.

Para repetir la prueba de PostgreSQL (requiere Docker):
```sh
cd backend
DEBUG=false VPV_V2_CONTAINER_TESTS=1 .venv/bin/pytest src/features/draft_assistant_v2/tests --confcutdir=src/features/draft_assistant_v2/tests --cov=src.features.draft_assistant_v2 -q
.venv/bin/coverage report --omit='*/tests/*'
```
El contenedor valida la tabla de historial y las leases; no sustituye una prueba del
upgrade completo de Alembic ni de consultas estadísticas contra datos representativos.

## Comparar jugadores

Hasta tres, elegidos con un buscador (nombre o equipo, mejor Prioridad
primero; `Enter` toma el primer resultado). Cuando la respuesta trae dos o
tres tarjetas se muestra una tabla comparativa: métricas en filas, jugadores
en columnas, el mejor valor de cada fila resaltado, más la fila de
**Confianza** con su motivo. La tarjeta lleva del servidor lo que la tabla
necesita (media, PJ, temporadas, titularidad, jornadas estimadas y las
banderas de cambio de equipo/posición); un backend antiguo sin esos campos
sigue parseando y la tabla muestra un guion donde falte el dato.
