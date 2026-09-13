# VPV — Propuesta integral de diseño visual y experiencia de usuario

**Fecha:** 13 de septiembre de 2026.  
**Objetivo:** una VPV más clara, competitiva y agradable de usar, conservando identidad, reglas, histórico y funcionalidades.

> Este documento reúne las ideas, decisiones y aprendizajes del trabajo de diseño. La implementación mencionada se realizó en la copia de evolución **`vpv_ai_codex`**, no se ha trasladado automáticamente al código de **`vpv_ai`**. Añadir este Markdown no supone desplegar ni integrar los cambios.

> **Estado a 13/09/2026:** el Inicio «Tu jornada» ya está portado a `vpv_ai` y en producción (#146–#151), sin la fuente Arial ni el modo simulación. Después, el playoff se adapta al momento de la jornada y la cabecera ocupa una línea (#152), y el Inicio sigue la jornada en juego con un único plazo efectivo del servidor (#153). Dos filas del §8 han cambiado: el ranking de goleadores fuera ya filtra `matches.counts` (#142), así que ese bloque ya no se oculta con partidos excluidos (#150); y una jornada migrada `completed` también cuenta como final (#147).

## 1. La idea central

El Inicio no debería ser una colección de enlaces ni un formulario de alineación ampliado. Debe responder a las preguntas que hacen volver a un participante durante la jornada:

- ¿Cómo voy y qué jugadores me quedan por puntuar?
- ¿Cómo van los demás respecto a mí?
- ¿Quién ha acertado con su once y quién ha dejado goles fuera?
- ¿Quién se ha comido un jugador que finalmente no ha jugado?
- Si estoy en playoff, ¿cómo va mi enfrentamiento y qué puede cambiarlo?
- Antes del cierre: ¿tengo mi alineación preparada y cuánto tiempo queda?

**La alineación es una tarea; seguir a los rivales es una motivación recurrente.** El diseño debe atender ambas cosas sin que una tape a la otra.

## 2. Decisiones acordadas y alcance

| Decisión | Estado |
|---|---|
| Primera evolución centrada en jugadores: Inicio, jornada, clasificación y alineación | Confirmada por el usuario |
| Rediseño progresivo, preservando identidad y funciones | Confirmada |
| Alternativa A «Tu jornada» como base | Elegida por el usuario |
| Comparación social, goles fuera, jugadores sin minutos y enfrentamiento personal como contenido central | Solicitado expresamente |
| Mejora visual real: composición, tipografía, CSS, contraste y adaptación móvil | Solicitada; una integración meramente funcional no bastaba |
| Sustituir toda la aplicación o cambiar de framework | Fuera de alcance |
| Publicar en producción o modificar reglas/permisos | No autorizado por estas decisiones de diseño |

Se exploraron dos alternativas con el mismo conjunto de datos ficticios:
- **A · Tu jornada:** prioriza la próxima acción personal y el contexto competitivo.
- **B · Club VPV:** prioriza el resumen de resultados.

La elección de A no significa dejar permanentemente un bloque enorme de alineación arriba. La prioridad cambia con el momento de la jornada.

## 3. Inicio adaptado al momento

### 3.1 Antes del cierre

1. Temporada y jornada inequívocas.
2. Estado personal: pendiente, guardada sin confirmar o confirmada, según datos reales.
3. Plazo efectivo y acción clara: **Preparar mi alineación**.
4. Próximo rival de playoff, si existe, sin adelantar datos no permitidos.
5. Resultados de la jornada anterior, identificados como anteriores.

Una vez confirmada, la alineación se convierte en una franja compacta. El sistema no debe seguir reclamando una tarea ya hecha. La proximidad del plazo puede aumentar el énfasis, pero sin avisos duplicados o colores de alarma permanentes.

### 3.2 Durante la jornada

El protagonismo pasa al enfrentamiento y a la comparación:
- Puntos personales de la jornada visible.
- Posición general y contexto de la liga.
- Jugadores pendientes de puntuar.
- Marcador del playoff personal, cuando corresponda.
- Participantes con puntos, diferencia respecto a ti y detalles de sus onces.
- Goleadores fuera del once y alineados sin minutos.

**40 puntos con ocho jugadores pendientes no cuentan la misma historia que 40 con uno.** No presentar los puntos como una cifra aislada.

### 3.3 Tras finalizar

Mostrar resultados finales solo cuando el estado lo permita. Ideas para la siguiente evolución:
- Puesto final de jornada y cambio en la clasificación general.
- Resultado del enfrentamiento y avance de la eliminatoria.
- Aciertos y oportunidades perdidas, con datos verificables.
- Próxima jornada y siguiente tarea, sin borrar el contexto de lo recién terminado.

Los cambios de puesto, resúmenes automáticos y explicaciones de eliminación son propuestas: requieren histórico y reglas contrastados, no inferencias del frontend.

## 4. Arquitectura visual del Inicio

### Escritorio

```text
Temporada / jornada                     Actualizar
Tu liga. Tu jornada.

[Tus puntos · JN] [Posición general] [Pendientes · JN]
[Alineación: estado compacto                 Acción]

┌────────────────────────────────┬─────────────────────┐
│ Tu playoff / enfrentamiento    │ Clasificación       │
│ Identidades + gran marcador    │ general             │
├────────────────────────────────┤                     │
│ Así va tu liga                 ├─────────────────────┤
│ Participantes y comparación    │ Accesos útiles      │
│ Once / banquillo desplegables  │ de la temporada     │
├────────────────────────────────┤                     │
│ Lo que marca diferencias      │                     │
└────────────────────────────────┴─────────────────────┘
Copa, grupos y economía cuando corresponda
```

La columna principal cuenta lo que está pasando; la lateral mantiene contexto. Evitar cards de ancho completo con una cifra en cada extremo y grandes superficies vacías.

### Móvil

- Una columna, sin reducir el escritorio hasta hacerlo ilegible.
- Cabecera única; quitar repetición del logotipo dentro del contenido si ya existe en navegación.
- Resumen breve y alineación confirmada compacta.
- Marcador suficientemente grande para entender el duelo de un vistazo.
- Comparación con nombres legibles, puntos alineados y fila personal destacada.
- Detalles bajo demanda; no cargar todas las plantillas al entrar.
- General y contenidos secundarios más abajo, sin perder acceso a ellos.

**Mejora pendiente:** la general completa después de la tabla de jornada alarga el scroll. Valorar resumen alrededor del puesto propio con «Ver todos», o cambio explícito Jornada/General. No ocultar participantes de forma irreversible: mirar al resto es parte del producto.

## 5. Bloques y microinteracciones

### 5.1 Resumen personal

Tres métricas principales: tus puntos, posición general y pendientes de puntuar. Cada dato de jornada debe indicar a cuál pertenece. Antes del cierre, si se muestra J3, no mezclar sus etiquetas con cifras ocultas de J4.

No inventar datos personales para visitantes, usuarios sin participación o respuestas fallidas. Usar ausencia explícita, no cero. La identidad personal se resuelve por participante de la temporada, no por nombre ni por ID de usuario.

### 5.2 Comparación entre participantes

- Mostrar a todos los participantes disponibles, no únicamente el podio.
- Destacar tu fila con fondo suave y marca lateral, además de texto identificativo.
- Alinear los puntos con cifras tabulares; mostrar diferencia respecto a ti con signo y explicación.
- Acompañar la puntuación con pendientes estadísticos y formación cuando sea útil.
- Permitir abrir varios participantes para consultar once y banquillo.
- Conservar abiertos los detalles al actualizar; no reiniciar la interacción cada minuto.
- Estado provisional visible, sin convertir cada fila en un párrafo de advertencias.

**Pendiente:** comparador lado a lado de tu once y el de un rival, con selección explícita y diferencias relevantes. La implementación actual permite desplegar participantes, no ofrece todavía ese comparador dedicado.

### 5.3 «Lo que marca diferencias»

Dos grupos separados visualmente:
1. **Goleadores fuera del once:** participante, jugador, goles y equipo.
2. **Alineados que no jugaron:** participante, jugador y contexto de ausencia confirmado por la fuente.

El lenguaje puede ser cercano a la liga («comidos»), pero la etiqueta debe explicar qué se está contando. No confundir dejar un goleador fuera con alinear a alguien que no participa.

Ideas posteriores: enlazar una incidencia al once correspondiente, filtrar por tu rival y resumir los eventos más relevantes. No convertirlo en un muro interminable ni atribuir errores a un usuario cuando faltan estadísticas.

### 5.4 Playoff personal

- Elegir enfrentamientos por participante y jornada, considerando todas las competiciones playoff de la temporada.
- Identidades a ambos lados, marcador protagonista y fase legible: cuartos, semifinales o final.
- Conservar la diferencia entre marcador ausente y cero.
- Añadir pendientes de ambos participantes cuando haya información de esa jornada.
- No reemplazar el marcador oficial del duelo con la puntuación de la tabla general o de jornada.
- Sin enfrentamiento asignado no equivale automáticamente a descanso.

**Pendiente:** explicar quién está decidiendo el duelo, mostrar jugadores restantes y resultado agregado cuando el formato lo requiera. No deducir clasificación/eliminación sin verificar formato, vueltas y desempates en backend.

### 5.5 Actualización y estados

Consulta periódica discreta y botón manual. Indicar si una hora corresponde a solicitud de actualización o a actualización de la fuente: no son lo mismo. No usar «En directo» sin una garantía real de frescura.

Carga, vacío, error y ausencia de permiso/participación deben tener mensajes distintos cuando el contrato permita diferenciarlos. Reintentar no debe conservar datos de otra temporada. Una consulta fallida no puede presentarse como «no has enviado alineación».

## 6. Lenguaje visual y CSS

### Identidad

Mantener VPV, su marca y su dualidad clara/oscura. No convertir una liga existente en una landing comercial. Evitar imágenes de stock, nuevos logotipos, degradados decorativos excesivos o animaciones que compitan con los resultados.

### Dirección aplicada en la copia de evolución

| Elemento | Dirección visual |
|---|---|
| Fondo y cards | Tokens existentes, separación por borde suave y espacio |
| Títulos | Jerarquía clara; cabecera de aproximadamente 30 px móvil / hasta 44 px escritorio |
| Marcador | Cifras tabulares de 40–64 px, alto contraste |
| Panel playoff | Azul noche `#102b4e`, texto claro y acentos suaves `#b5efdc` |
| Texto principal claro | Azul tinta `#16324f`; adaptación al tema oscuro |
| Identidad de equipos | Monogramas decorativos; no necesitan fotos ni llamadas externas |
| Cancha decorativa | Líneas CSS muy sutiles, sin interferir con texto ni interacción |
| Fila propia | Fondo tenue, marca lateral y etiqueta textual |
| Incidencias | Subpaneles diferenciados, iconos simples y contenido escaneable |
| Explicaciones | Ayuda desplegable en vez de párrafos siempre visibles |
| Controles | Foco visible y áreas táctiles principales de 44 px |

Usar CSS Modules para aislar esta evolución y reutilizar tokens existentes. No añadir dependencias visuales por defecto ni cambiar estilos globales incidentalmente.

La densidad no consiste en hacer toda la letra diminuta. Se aumentaron nombres y metadatos después de revisar móvil. Continuar validando textos de 10–11 px, zoom, nombres largos y lectura real; el hecho de que algo quepa no demuestra que sea cómodo.

## 7. Navegación y experiencia transversal

- Conservar temporada en enlaces, recargas y rutas compartidas mediante `?season=`.
- Eliminar cabeceras y accesos duplicados; cada bloque debe aportar información o una tarea distinta.
- Mantener Copa, grupos y economía sin darles el mismo peso que el seguimiento diario.
- Economía solo cuando la temporada tenga esa mecánica habilitada.
- Valorar navegación inferior móvil para Inicio/Jornada/Clasificación/Alineación, pero auditar primero el shell existente y evitar dos navegaciones que compitan. Es propuesta, no parte del cambio realizado.
- Aplicar después la misma jerarquía a Jornada, Clasificación y edición de Alineación: no rediseñar todo simultáneamente.
- Separar tareas de gestión delegada, participación y analítica de administración. El diseño no debe ampliar permisos ni suponer que todo se resuelve con «administrador sí/no».

## 8. Reglas de datos que condicionan el diseño

Estos hallazgos se verificaron en la copia de evolución; contrastarlos de nuevo antes de portar código:

| Dato o estado | Precaución necesaria |
|---|---|
| `pending_players` | Cuenta pendientes de estadísticas; no garantiza que todavía no hayan jugado |
| Puntos cero | No demuestran cero minutos ni ausencia |
| `score_breakdown == null` | Desglose no disponible; no implica que no participó |
| Plazo | Usar el plazo efectivo del servidor, incluyendo overrides; `null` no significa vencido |
| Jornada final | En el contrato inspeccionado: `status == finished` y `stats_ok` |
| Ganador en playoff | Su presencia no garantiza que toda la jornada sea definitiva |
| ID de usuario | No equivale a ID de participante de temporada |
| Totales de rankings | Pertenecen a temporada; filtrar los detalles por jornada |
| Goleadores fuera | El ranking inspeccionado no filtra `matches.counts`; se oculta este bloque si hay partidos excluidos |
| Jugadores sin minutos | Reutilizar el ranking backend, no deducirlos desde puntuaciones |
| Alineaciones rivales | Ocultarlas en UI antes del plazo no sustituye autorización en servidor |

**Riesgo pendiente:** las lecturas públicas heredadas de matchdays/rankings/competitions necesitan revisión de política y permisos antes de producción. No afirmar que este rediseño blinda el acceso directo a datos.

## 9. Estado real: qué existe y qué falta

### Implementado únicamente en `vpv_ai_codex`

Cabecera y composición nuevas, métricas por jornada visible, alineación compacta, marcador personal, general lateral, comparación desplegable, incidencias, estilos claros/oscuros, navegación contextual y refresco que conserva expansión. No se cambiaron reglas ni endpoints backend para conseguirlo.

### Propuestas pendientes

Comparador lado a lado; síntesis de quién decide el duelo; variación histórica de puestos; resultado agregado de eliminatorias; resumen posjornada; refinamiento del scroll de general móvil; navegación inferior; extensión coherente del diseño a los otros recorridos diarios.

No se incluyen nuevas predicciones, proveedores de pago, notificaciones push ni una reescritura tecnológica.

## 10. Criterios de aceptación y validación

- Reconocer temporada, jornada, estado de alineación y carácter provisional/final sin interpretar el layout.
- Distinguir puntos, pendientes estadísticos y jugadores que no participaron.
- Comparar participantes y conservar el contexto al actualizar o navegar.
- Mantener datos reales, mensajes honestos y errores recuperables.
- Sin desbordamiento horizontal a 320, 390 y 1440 px; revisar nombres largos y varios participantes.
- Verificar foco, teclado, zoom y ambos temas; no comunicar significado únicamente mediante color.
- Comparar capturas nativas de viewport además de capturas largas, que reducen demasiado la tipografía.
- Esperar a que termine la transición al capturar modo oscuro: una imagen intermedia gris falsea la evaluación.
- Medir después tiempos y éxito de tareas con usuarios; no prometer mejoras porcentuales sin baseline comparable.

En la copia de evolución se verificaron **226 tests frontend**, tipos y build; **19 tests de tooling**; lint sin errores con cinco avisos heredados. Chromium comprobó ocho participantes y tres tamaños, rail lateral, alineación confirmada menor de 125 px, marcador de al menos 40 px, refresco y temas claro/oscuro.

**Límites de esa evidencia:** API sintética en navegador, no E2E completo con BD real; no certificación WCAG ni auditoría de lector de pantalla; esas pruebas no se han ejecutado sobre `vpv_ai` al añadir este documento. La general completa sigue generando scroll móvil. Las capturas históricas usan fixtures diferentes: no comparar sus alturas totales como medida de mejora.

## 11. Referencias para una futura integración

Archivos de referencia dentro de **`vpv_ai_codex`**:
- `frontend/src/app/page.tsx`: composición del Inicio y contenidos secundarios.
- `frontend/src/components/dashboard/competitive-home.tsx`: estado/contexto y distribución.
- `frontend/src/components/dashboard/home.module.css`: sistema visual acotado.
- `frontend/src/components/dashboard/personal-playoff.tsx` y `.module.css`: marcador deportivo.
- `frontend/src/components/dashboard/matchday-accordion.tsx`: comparación y detalle de onces.
- `frontend/src/components/dashboard/matchday-incidents.tsx`: incidencias por jornada.
- `frontend/src/components/dashboard/podium.tsx`: general lateral.
- `tools/design-browser/home-smoke.cjs`: pruebas visuales con API sintética.
- `docs/INICIO_COMPETITIVO.md`: contratos, evidencias y límites de implementación.

Para integrarlo aquí: revisar diferencias actuales, portar por componentes pequeños, comprobar contratos y permisos, ejecutar regresiones y revisar capturas con el mismo escenario. **No copiar toda la aplicación ni considerar este documento una autorización de despliegue.**

## 12. Aprendizajes de diseño

1. Integrar más funcionalidades no equivale a mejorar la UX: hay que decidir qué ve primero cada usuario.
2. El interés competitivo exige ver a los demás, no solo una tarjeta personal o el líder.
3. El contexto de los puntos importa tanto como la cifra.
4. Una tarea completada debe ocupar menos espacio que una pendiente.
5. El marcador y las comparaciones merecen jerarquía propia, no otra card genérica.
6. Lo no disponible debe parecer no disponible, no un resultado negativo o un cero definitivo.
7. Refrescar y cambiar de pantalla no debe borrar la interacción ni la temporada elegida.
8. La calidad visual exige revisar pantallas reales, no deducirla de tests verdes.
