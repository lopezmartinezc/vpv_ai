"use client";

import { type ReactNode, useState } from "react";

/**
 * In-app manual for every statistic in the admin stats dashboard: what each
 * metric measures, how to read it, and what counts as a good/bad value.
 * Thresholds match the backend (service_draft signal rules, scorecard tiers,
 * advanced-metrics confidence). Static content — no data fetch.
 */

function Section({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-vpv-card-border bg-vpv-card">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div>
          <h3 className="text-sm font-semibold text-vpv-text">{title}</h3>
          {subtitle && <p className="text-xs text-vpv-text-muted">{subtitle}</p>}
        </div>
        <span className="text-vpv-text-muted">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-vpv-border/50 px-4 py-3 text-xs leading-relaxed text-vpv-text-muted">
          {children}
        </div>
      )}
    </div>
  );
}

function Metric({
  name,
  good,
  children,
}: {
  name: string;
  good?: string;
  children: ReactNode;
}) {
  return (
    <div className="border-t border-vpv-border/30 pt-2 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-semibold text-vpv-text">{name}</span>
        {good && (
          <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-300">
            {good}
          </span>
        )}
      </div>
      <p className="mt-0.5">{children}</p>
    </div>
  );
}

const CHEAT: { m: string; good: string; bad: string }[] = [
  { m: "Prioridad (columna maestra)", good: "alta — total proyectado ajustado por riesgo", bad: "baja / — sin proyección" },
  { m: "PtsRes (resto de temporada)", good: "alto", bad: "bajo pese a buen valor → pocos minutos" },
  { m: "VORP (escasez posicional)", good: "alto (> 0)", bad: "≈ 0 (nivel reemplazo)" },
  { m: "Disponibilidad", good: "> 85% (titular fijo)", bad: "< 60% (riesgo rotación)" },
  { m: "Fiabilidad (evento vs nota)", good: "alta — puntos repetibles", bad: "baja — depende de la nota" },
  { m: "DefEq — defensa del equipo (porteros)", good: "< 1.1 goles/partido (muro)", bad: "> 1.4 (colador)" },
  { m: "Tendencia interanual", good: "> +10% (mejora)", bad: "< −15% (declive)" },
  { m: "Confianza (xPts)", good: "alta", bad: "baja (< 5–10 partidos)" },
];

export function StatsGuide() {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card px-4 py-3">
        <h2 className="text-sm font-semibold text-vpv-text">
          📖 Guía de estadísticas
        </h2>
        <p className="mt-1 text-xs text-vpv-text-muted">
          Qué mide cada cosa, cómo leerla y qué valores son buenos. Todo sirve a
          dos objetivos: <b className="text-vpv-text">preparar el draft</b> (elegir la
          mejor plantilla) y <b className="text-vpv-text">entender el rendimiento</b>{" "}
          durante la temporada. El modelo de draft está validado con backtests
          sobre 8 temporadas reales: la mezcla histórico⊕actual (Spearman ~0.83 a
          4–8 jornadas) y el orden por <b className="text-vpv-text">Prioridad</b>{" "}
          (total proyectado), que predice los puntos reales mejor que el valor por
          partido (0.45 vs 0.35).
        </p>
      </div>

      {/* Cheat sheet — always visible */}
      <div className="overflow-x-auto rounded-lg border border-vpv-card-border bg-vpv-card">
        <div className="border-b border-vpv-border px-4 py-2 text-xs font-semibold text-vpv-text">
          Hoja rápida de “buenos valores”
        </div>
        <table className="w-full text-xs">
          <thead className="bg-vpv-bg/40 text-vpv-text-muted">
            <tr>
              <th className="px-3 py-1.5 text-left">Métrica</th>
              <th className="px-3 py-1.5 text-left">Bueno</th>
              <th className="px-3 py-1.5 text-left">Malo / ojo</th>
            </tr>
          </thead>
          <tbody>
            {CHEAT.map((r) => (
              <tr key={r.m} className="border-t border-vpv-border/40">
                <td className="px-3 py-1.5 font-medium text-vpv-text">{r.m}</td>
                <td className="px-3 py-1.5 text-emerald-300">{r.good}</td>
                <td className="px-3 py-1.5 text-red-300">{r.bad}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Section
        title="1 · Cómo elegir en el draft (paso a paso)"
        subtitle="El flujo recomendado en la pestaña «Draft»"
        defaultOpen
      >
        <ol className="ml-4 list-decimal space-y-1.5">
          <li>
            <b className="text-vpv-text">Ordena por Prioridad</b> (columna maestra, orden
            por defecto). Es el <i>total proyectado el resto de temporada</i> (valor por
            partido × partidos esperados) con descuentos de riesgo. Ordenar por total —no
            por valor por partido— predice mejor los puntos que sumas (backtest 8
            temporadas). Prioridad alta = pick prioritario.
          </li>
          <li>
            <b className="text-vpv-text">Descuentos de riesgo</b> que ya lleva la Prioridad:
            <span className="text-vpv-text-muted"> PICO (año atípico) −10%, riesgo banquillo
            −25%, fiabilidad baja −8%.</span> Por eso una estrella con banderas rojas baja.
          </li>
          <li>
            <b className="text-vpv-text">Escasez con VORP</b>: el VORP (valor sobre el
            reemplazo de su posición) te dice <i>cuándo</i> conviene gastar un pick en una
            posición — pocas opciones por encima del reemplazo = draftea antes. Mira el
            resumen de «Escasez por posición» arriba.
          </li>
          <li>
            <b className="text-vpv-text">Rol y fiabilidad</b>: Disponibilidad alta (titular
            fijo) manda; y prefiere puntos de <i>eventos</i> (goles, asistencias, portería a
            cero) sobre nota Marca/AS (Fiabilidad alta = repetible).
          </li>
          <li>
            <b className="text-vpv-text">Porteros: por la defensa del equipo</b>, no por su
            fama. Mira <b className="text-vpv-text">DefEq</b> (goles que encaja su equipo):
            menos = mejor. Un titular de equipo con buena defensa suma clean sheets. Su
            valor ya lo capta la Prioridad (disponibilidad + defensa).
          </li>
          <li>
            <b className="text-vpv-text">Banderas</b>: NUEVO (sin histórico), +EQ / +POS
            (cambió equipo/posición), PICO (riesgo regresión), PEN (lanza penaltis), 🪑
            (riesgo banquillo).
          </li>
        </ol>
      </Section>

      <Section
        title="2 · Columnas del tablero de draft"
        subtitle="Glosario de la pestaña «Draft»"
      >
        <Metric name="Prioridad (Prio)" good="alta = pick prioritario">
          Columna maestra y orden por defecto. Puntos proyectados el resto de temporada
          (valor × partidos esperados) con descuentos de riesgo (PICO, banquillo,
          fiabilidad). Ordenar por total proyectado predice los puntos reales mejor que el
          valor por partido (backtest 8 temporadas: 0.45 vs 0.35).
        </Metric>
        <Metric name="DefEq (defensa del equipo)" good="< 1.1 goles/partido">
          Goles que encaja el equipo por partido (temporada pasada; media de la liga como
          prior para ascendidos). Es el factor clave del portero (correlación −0.83 con sus
          puntos): menos goles encajados = más portería a cero = más puntos.
        </Metric>
        <Metric name="Ronda" good="baja = se va antes">
          Ronda estimada de draft = puesto global por Prioridad ÷ nº de participantes. Al
          pasar el ratón, el pick global.
        </Metric>
        <Metric name="Tier" good="Elite / Sólido">
          Tier posicional (elite / sólido / normal / flojo). Los porteros salen «Equipo»:
          su valor depende del equipo, no de una escala de puntos.
        </Metric>
        <Metric name="VORP (escasez)" good="alto = posición escasa">
          Valor sobre reemplazo posicional = valor proyectado − valor del jugador de
          reemplazo en su posición (el Nº 35 en POR, 90 en DEF/MED, 70 en DEL). Ya no es
          el orden maestro (lo es Prioridad), pero sí el diagnóstico de <i>escasez</i>:
          pocas opciones con VORP &gt; 0 en una posición = draftéala antes.
        </Metric>
        <Metric name="PtsRes" good="alto">
          Puntos proyectados del resto de temporada = valor por partido × partidos
          esperados restantes (jornadas que quedan × disponibilidad).
        </Metric>
        <Metric name="Fiab (fiabilidad)" good="alta = repetible">
          % de puntos por eventos concretos vs nota Marca/AS. Los puntos por nota son
          más subjetivos/ruidosos.
        </Metric>
        <Metric name="Ens (ensemble)">
          Valor proyectado por partido: mezcla de histórico + temporada actual con
          «shrinkage» (peso actual = n/(n+4)). Es el mejor predictor individual.
        </Metric>
        <Metric name="Avg">Media simple de pts/partido de la temporada anterior (baseline).</Metric>
        <Metric name="Form">Forma de la 2ª mitad (J20–J38): predice el arranque siguiente.</Metric>
        <Metric name="Stab">Estabilidad: premia minutos altos y constantes (menor riesgo de banquillo).</Metric>
        <Metric name="Prod">Productividad: valor bonificado por goles+asistencias por 90 min.</Metric>
        <Metric name="Trend" good="> +10% mejora; < −15% declive">
          Tendencia interanual: % de mejora o declive respecto a la temporada previa.
        </Metric>
        <Metric name="Disp (disponibilidad)" good="> 85%; < 60% = riesgo">
          % de partidos con 45+ minutos jugados. Mide si es titular fijo o rota.
        </Metric>
        <Metric name="Cons (consistencia)" good="> 0.6 fiable; < 0.3 volátil">
          1 − CV (coeficiente de variación). 1 = muy regular, 0 = impredecible.
        </Metric>
        <Metric name="Marca / AS">Nota mediática media (estrellas Marca 1–4, picas AS).</Metric>
      </Section>

      <Section
        title="3 · Composición y formaciones"
        subtitle="cuántos por posición y qué once puntúa más"
      >
        <p>
          Reparto recomendado (26): <b className="text-vpv-text">2 POR · 8 DEF · 7-8 MED ·
          6-7 DEL</b>. Suele infra-draftearse el delantero: la mejor formación pide 3 y
          hace falta fondo para poder alinearlos siempre.
        </p>
        <p className="mt-2">
          Formaciones que más puntúan (datos reales): <b className="text-vpv-text">1-4-3-3</b>{" "}
          y <b className="text-vpv-text">1-3-4-3</b> (3 delanteros). El delantero titular
          aporta más que el resto de posiciones, así que juega 3 siempre que puedas.
        </p>
        <p className="mt-2">
          Portero: solo ~12 titulares fijos por temporada (posición escasa); un titular fijo
          suma de los más puntos totales de la liga. Elígelo por la <b className="text-vpv-text">
          defensa del equipo</b> (DefEq), no por su fama.
        </p>
      </Section>

      <Section
        title="4 · Tiers posicionales"
        subtitle="referencia de nivel por posición"
      >
        <Metric name="Tiers">
          Elite (top 10%), Sólido (top 25%), Promedio (top 50%), Reemplazable (resto).
          Por pts/partido: DEF 6.6 / 5.8 / 4.9 · MED 6.1 / 5.3 / 4.4 · DEL 7.2 / 5.4 / 4.2.
        </Metric>
        <Metric name="Escasez (scarcity)">
          Cuántos «elite» hay por posición. Cuanto menos, más valor tiene asegurar uno
          pronto. El POR suele ser el más escaso y dependiente del equipo.
        </Metric>
      </Section>

      <Section
        title="5 · Métricas avanzadas del jugador"
        subtitle="pestaña «Avanzado»"
      >
        <Metric name="pp90">Puntos por 90 minutos: normaliza por tiempo jugado (útil para suplentes con buen rendimiento).</Metric>
        <Metric name="Percentiles p10 / p50 / p90">Suelo / mediana / techo de su distribución de puntos por jornada.</Metric>
        <Metric name="CV / Consistencia">Dispersión relativa. Suelo alto (p10) + CV bajo = pick seguro; techo alto (p90) + CV alto = lotería.</Metric>
        <Metric name="Forma (EWMA-5)">Media exponencial de las últimas 5 jornadas (pesa más lo reciente).</Metric>
        <Metric name="Tendencia">rising si forma &gt; media×1.1, falling si &lt; media×0.9, estable en medio.</Metric>
        <Metric name="IC 95%">Intervalo de confianza de su media: cuánto te puedes fiar del promedio con los partidos que lleva.</Metric>
      </Section>

      <Section
        title="6 · Predicción de jornada (xPts)"
        subtitle="En «Mis predicciones» y el widget de deadline"
      >
        <Metric name="xPts (+ suelo / techo)">Puntos esperados para la próxima jornada; suelo/techo = ± desviación típica.</Metric>
        <Metric name="Dificultad del rival">rival_factor y etiqueta fácil / medio / difícil según goles encajados del rival (media temporada + últimos 5).</Metric>
        <Metric name="starter %">% de titularidades recientes (45+ min en los últimos 5) — descuenta riesgo de rotación.</Metric>
        <Metric name="Lanzador de penaltis">marcó ≥ 1 penalti esta temporada — bonus de techo.</Metric>
        <Metric name="Confianza" good="alta">
          baja si &lt; 5 partidos; media si &lt; 10 o CV ≥ 0.5; alta si CV &lt; 0.3.
        </Metric>
      </Section>

      <Section title="7 · Contexto" subtitle="Splits, dependencia y comparador">
        <Metric name="Splits casa / fuera">Rendimiento local vs visitante. (Ancla el equipo por jornada, así que un traspaso no falsea el pasado.)</Metric>
        <Metric name="Dependencia de equipo">% de los puntos del equipo que dependen de su máximo anotador. Alta dependencia = riesgo si ese jugador falla.</Metric>
        <Metric name="Comparador (radar)">Compara varios jugadores en 6 ejes normalizados: goles, asistencias, media, consistencia, pp90 y forma.</Metric>
      </Section>

      <Section title="8 · Draft Retro (histórico)" subtitle="pestaña «Draft Retro»">
        <Metric name="Curva de valor por pick">Puntos medios que rinde cada número de pick a lo largo de las temporadas (la referencia de un slot).</Metric>
        <Metric name="Bust / Steal rate">% de picks tempranos (1–3) por debajo de la mediana (bust) y de picks tardíos por encima de la mediana de rondas altas (steal).</Metric>
        <Metric name="Delta vs slot / tag">Cuánto rindió un pick por encima/debajo de lo esperado de su slot; etiqueta steal / normal / bust.</Metric>
        <Metric name="IQ del participante">Suma de deltas vs slot: quién acierta más en el draft, y en qué rondas.</Metric>
        <Metric name="Backtest (Spearman)">Correlación entre lo que predijo el modelo y lo que ocurrió de verdad. ~0.83 a 4–8 jornadas.</Metric>
      </Section>

      <Section title="9 · Cómo funciona el modelo" subtitle="Metodología">
        <p>
          El draft de Liga se hace con <b className="text-vpv-text">4–8 jornadas</b>{" "}
          jugadas, así que el modelo <b className="text-vpv-text">mezcla histórico +
          temporada actual</b> con «shrinkage»: el peso de lo actual = n/(n+4), donde n
          son los partidos jugados. A 4 jornadas la actual pesa ~50%, a 8 ~67%. Validado
          con backtest sobre 6 temporadas reales: Spearman ~0.83 (vs ~0.76 usando solo
          histórico).
        </p>
        <p>
          El orden lo manda la <b className="text-vpv-text">Prioridad</b> (total proyectado
          + descuentos de riesgo); el <b className="text-vpv-text">VORP</b> diagnostica la
          escasez por posición, <b className="text-vpv-text">PtsRes</b> es el total sin
          ajustar, y la <b className="text-vpv-text">Fiabilidad</b> separa el punto repetible
          del punto por nota. El equipo de cada jornada queda anclado en el histórico, así
          que los traspasos a mitad de temporada no reescriben el pasado.
        </p>
      </Section>
    </div>
  );
}
