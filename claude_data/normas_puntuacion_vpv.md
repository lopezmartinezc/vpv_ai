# Normas de Puntuación - Liga VPV Fantasy

## 📊 Puntuación Base

### Participación
- **Jugar el partido**: +1 punto (`ptos_jugar`)
- **Titular** (iniciar el partido o jugar 90 minutos completos): +1 punto (`ptos_titular`)
  - Si sale de **suplente** (evento "Entrada"): NO recibe punto de titular
  - Si es **sustituido** (evento "Salida"): SÍ recibe punto de titular

### Resultado del Equipo
- **Victoria**: +2 puntos (`ptos_resultado`)
- **Empate**: +1 punto (`ptos_resultado`)
- **Derrota**: 0 puntos (`ptos_resultado`)

## ⚽ Puntuación por Posición

### Goles Marcados (`ptos_gol`)
| Posición | Puntos por Gol |
|----------|----------------|
| Portero (POR) | +10 puntos |
| Defensa (DEF) | +8 puntos |
| Mediocampista (MED) | +7 puntos |
| Delantero (DEL) | +5 puntos |

### Portería a Cero - Imbatibilidad (`ptos_imbatibilidad`)

#### Porteros (POR)
- **0 goles encajados** Y **mínimo 65 minutos jugados**: +4 puntos
- **1 gol encajado**: 0 puntos
- **Más de 1 gol encajado**: Penalización igual al número de goles encajados (ej: 3 goles = -3 puntos)

#### Defensas (DEF)
- **0 goles encajados** Y **mínimo 45 minutos jugados**: +3 puntos
- **Con goles encajados**: 0 puntos (sin penalización)

#### Mediocampistas (MED) y Delanteros (DEL)
- No reciben puntos por imbatibilidad

## 🎯 Acciones Especiales

### Acciones Positivas
| Acción | Puntos | Variable |
|--------|--------|----------|
| **Gol de penalti** | +5 puntos | `ptos_gol_p` |
| **Asistencia** | +2 puntos | `ptos_asis` |
| **Penalti parado** (solo POR) | +5 puntos | `ptos_pen_par` |
| **Tiro al palo** | +1 punto | `ptos_tiro_palo` |
| **Penalti forzado** | +1 punto | `ptos_pen_for` |

### Acciones Negativas
| Acción | Puntos | Variable |
|--------|--------|----------|
| **Penalti fallado** | -3 puntos | `ptos_pen_fall` |
| **Gol en propia meta** | -2 puntos | `ptos_gol_pp` |
| **Tarjeta amarilla** | -1 punto | `ptos_ama` |
| **Doble amarilla** | -3 puntos | `ptos_roja` |
| **Tarjeta roja directa** | -3 puntos | `ptos_roja` |
| **Penalti cometido** | -1 punto | `ptos_pen_com` |

### Casos Especiales
- **Amarilla quitada por el comité** (`ama_remove`): Se registra pero NO afecta la puntuación

## 📈 Valoración Mediática

### Nota del Diario Marca (`est_marca` / `ptos_marca`)
- ⭐ (1 estrella): +1 punto
- ⭐⭐ (2 estrellas): +2 puntos
- ⭐⭐⭐ (3 estrellas): +3 puntos
- ⭐⭐⭐⭐ (4 estrellas): +4 puntos
- **"-"** (No jugó): -1 punto
- **"SC"** (Sin calificar): 0 puntos

### Picas del Diario AS (`picas_as` / `ptos_as`)
- Cada pica 🔴: +1 punto (pueden ser múltiples)
- **"-"** (No jugó): -1 punto
- **"SC"** (Sin calificar): 0 puntos

### Puntuación Combinada Marca + AS (`marca_as`)
- Suma de `ptos_marca` + `ptos_as`

## 📋 Tiempo de Juego y Eventos

### Registro de Tiempo (`tiempo_jug`)
- **Titular sin cambio**: 90 minutos
- **Sustituido** (evento "Salida"): Minutos jugados hasta la sustitución
- **Suplente** (evento "Entrada"): 90 - minuto de entrada

### Eventos Registrados
- **`evento`**: "Entrada" o "Salida"
- **`min_evento`**: Minuto en que ocurrió el cambio
- **`play`**: 1 si jugó, 0 si no jugó

## 🔢 Cálculo Final

**`ptos_jor` (Puntuación Total de la Jornada)** = 
- `ptos_jugar` 
- + `ptos_titular` 
- + `ptos_resultado` 
- + `ptos_imbatibilidad`
- + `ptos_gol` 
- + `ptos_gol_p` 
- + `ptos_asis`
- + `ptos_pen_par`
- + `ptos_tiro_palo`
- + `ptos_pen_for`
- + `ptos_pen_fall` (negativo)
- + `ptos_gol_pp` (negativo)
- + `ptos_ama` (negativo)
- + `ptos_roja` (negativo)
- + `ptos_pen_com` (negativo)
- + `ptos_marca`
- + `ptos_as`

## 🔄 Sistema de Actualización y Control

### Estado de las Estadísticas
- **`estadistica`**: 0 = no procesado, 1 = procesado
- **`est_ok`** (en `list_jornadas_temp`): 0 = pendiente, 1 = completado
- Un partido se marca como completo (`est_ok = 1`) cuando tiene menos de 12 valores "SC"

### Datos del Partido
- **`res_l`**: Goles del equipo local
- **`res_v`**: Goles del equipo visitante
- **`res`**: Resultado (2 = victoria, 1 = empate, 0 = derrota)
- **`gol_f`**: Goles a favor del equipo del jugador
- **`gol_c`**: Goles en contra del equipo del jugador

## 📊 Campos de Conteo (no suman puntos directamente)
- **`gol`**: Número de goles marcados (no penaltis)
- **`gol_p`**: Número de goles de penalti
- **`pen_fall`**: Número de penaltis fallados
- **`gol_pp`**: Número de goles en propia meta
- **`asis`**: Número de asistencias
- **`pen_par`**: Número de penaltis parados
- **`ama`**: Si recibió amarilla (1 = sí, 0 = no)
- **`ama_remove`**: Si le quitaron la amarilla (1 = sí, 0 = no)
- **`ama_doble`**: Si recibió doble amarilla (1 = sí, 0 = no)
- **`roja`**: Si recibió roja directa (1 = sí, 0 = no)
- **`tiro_palo`**: Número de tiros al palo
- **`pen_for`**: Número de penaltis forzados
- **`pen_com`**: Número de penaltis cometidos
