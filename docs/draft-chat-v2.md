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
  `ASSISTANT_V2_QUICK_EFFORT=low`, `ASSISTANT_V2_MAX_ROUNDS=20`,
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

  `QUICK_EFFORT` es el esfuerzo de razonamiento que se pide a OpenAI en modo
  *Rápido* (`low` | `medium` | `high`; vacío no envía el parámetro, para un
  modelo que no lo acepte). El modo detallado lo deja al proveedor. Anthropic
  no lo usa: V2 no activa *thinking* ahí. La primera respuesta real tardó
  77 s a esfuerzo por defecto — medio reloj de pick — en una pregunta marcada
  como rápida.

## Coste por ronda

La línea de consumo muestra los tokens de entrada **y cuántos sirvió el
proveedor desde su caché de prefijo** (`cached_tokens` en OpenAI,
`cache_read_input_tokens` en Anthropic). El total no es la factura; la
parte en caché se cobra a una fracción.

La evidencia inicial (`estado_draft` + `evaluar_pick`) va en el **prompt de
sistema**, delante de herramientas e historial, y **sin marca de tiempo**
(los hashes de revisión bastan). Es idéntica para toda pregunta sobre la
misma revisión del draft, y como los proveedores cachean por prefijo exacto,
así se reutiliza entre consultas consecutivas en un mismo pick — y deja de
reutilizarse justo cuando el draft cambia, que es cuando debe. En el último
mensaje de usuario nunca lo era: el historial que va delante la desplazaba
cada vez (medido: 7 936 tokens en caché en dos preguntas seguidas, ni uno
de la evidencia reutilizado). La línea de modo (rápido/detallado) va al final
del sistema, para que las dos modalidades compartan reglas y evidencia.

En OpenAI cada request lleva además `prompt_cache_key`, estable por draft y
revisión. Según la documentación de OpenAI la clave **particiona** la
reutilización de caché entre grupos de peticiones (el enrutado lo gestiona
OpenAI) y conviene que las peticiones relacionadas compartan una. Una clave por
estado del draft mantiene todas las preguntas de ese estado en la misma
partición; el primer acierto cruzado medido en producción (0 → 17 280 tokens
en caché, 83 %) llegó con ella. Cambia exactamente cuando cambia el draft.

Los campos de `usage` no significan lo mismo en los dos proveedores y se
normalizan: *entrada* es todo lo enviado (en Anthropic, `input_tokens` es solo
lo no cacheado y hay que sumar lecturas y escrituras de caché), *en caché* lo
leído de caché, y se acumulan aparte las escrituras (`cache_write_tokens` en
OpenAI, `cache_creation_input_tokens` en Anthropic, que las cobra a 1,25×).

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

## Correcciones de revisión
- Los errores externos registran proveedor, modelo, estado HTTP y los campos
  **estructurados** del error (`type`, `code`, `param`), nunca el texto libre del
  mensaje —que es donde un proveedor puede devolver lo que le enviamos—. Un cuerpo
  que no sea JSON no aporta nada al log.
- `plantillas` permite `participant_id`, `offset` y `limit` (máximo 30, por defecto 26,
  que es una plantilla completa). Con filtro, una plantilla entera cabe en una sola
  llamada; sin filtro se pagina con `next_offset` hasta `null`, y cada página tiene su
  propia referencia de evidencia. Las necesidades por formación viajan **solo en la
  primera página**: son idénticas en todas y pesan más que los jugadores de una.
- Las tarjetas se ocultan mientras la revisión está pendiente o falla, y se invalidan
  inmediatamente cuando cambia el evento del draft.
- `ASSISTANT_V2_TIMEOUT_SECONDS` admite como máximo **170 segundos**, con 20 segundos
  de margen respecto al navegador, y `ASSISTANT_V2_PROVIDER_TIMEOUT_SECONDS` no puede
  superarlo. **Revisar overrides antes de reiniciar producción:** un valor mayor hace
  fallar la validación al arrancar, y `AssistantSettings` se construye al importar, así
  que se cae el backend entero, no solo V2. Por defecto 150 y 90, que no requieren
  ninguna variable.
