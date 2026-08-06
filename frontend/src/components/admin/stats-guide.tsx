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
  { m: "VORP (columna maestra)", good: "alto (> 0)", bad: "≈ 0 (nivel reemplazo)" },
  { m: "PtsRes (resto de temporada)", good: "alto", bad: "bajo pese a buen valor → pocos minutos" },
  { m: "Disponibilidad", good: "> 85% (titular fijo)", bad: "< 60% (riesgo rotación)" },
  { m: "Consistencia (1−CV)", good: "> 0.6 (fiable)", bad: "< 0.3 (lotería)" },
  { m: "Fiabilidad (evento vs nota)", good: "alta — puntos repetibles", bad: "baja — depende de la nota" },
  { m: "Tendencia interanual", good: "> +10% (mejora)", bad: "< −15% (declive)" },
  { m: "Señal", good: "strong_buy / buy", bad: "avoid" },
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
          durante la temporada. El modelo de draft está validado con un backtest
          sobre 6 temporadas reales (Spearman ~0.83 a 4–8 jornadas).
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
        subtitle="El flujo recomendado en la pestaña «Draft Valor»"
        defaultOpen
      >
        <ol className="ml-4 list-decimal space-y-1.5">
          <li>
            <b className="text-vpv-text">Ordena por VORP</b> (columna maestra). Es el
            valor que da un jugador <i>por encima del reemplazo de su posición</i>, así
            que compara POR/DEF/MED/DEL en un solo eje. VORP alto = pick prioritario;
            ≈ 0 = «lo mismo que hay disponible después».
          </li>
          <li>
            <b className="text-vpv-text">Mira PtsRes</b> (puntos del resto de temporada
            = valor proyectado × partidos esperados). Es el objetivo real. Un jugador
            con gran valor por partido pero pocos minutos baja aquí.
          </li>
          <li>
            <b className="text-vpv-text">Ajusta por riesgo</b> según tu turno en el
            snake: picks tempranos → <i>seguro</i> (Disponibilidad y Consistencia altas);
            picks tardíos → <i>lotería</i> (techo alto aunque el suelo sea bajo).
          </li>
          <li>
            <b className="text-vpv-text">Comprueba la Fiabilidad</b>: cuántos de sus
            puntos vienen de eventos concretos (goles, asistencias, portería a cero) vs
            nota mediática. Alto = repetible; bajo = depende de notas subjetivas.
          </li>
          <li>
            <b className="text-vpv-text">Usa la Señal como filtro rápido</b>{" "}
            (strong_buy / buy / hold / avoid), no como verdad absoluta.
          </li>
        </ol>
      </Section>

      <Section
        title="2 · Columnas del tablero de draft"
        subtitle="Glosario de la pestaña «Draft Valor»"
      >
        <Metric name="VORP" good="alto = pick prioritario">
          Valor sobre reemplazo posicional = valor proyectado − valor del jugador de
          reemplazo en su posición (el Nº 35 en POR, 90 en DEF/MED, 70 en DEL). Hace
          comparables las posiciones.
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
        title="3 · Señal de draft — cómo se calcula"
        subtitle="strong_buy · buy · hold · avoid"
      >
        <p>
          Se cuentan señales positivas y negativas y se resume:
        </p>
        <ul className="ml-4 list-disc space-y-1">
          <li>
            <span className="text-emerald-300">Positivas</span>: ensemble +5% sobre la
            media · tendencia &gt; +10% · disponibilidad &gt; 85% · consistencia &gt; 0.6
            · ≥ 3 temporadas de historial.
          </li>
          <li>
            <span className="text-red-300">Negativas</span>: en declive &lt; −15% ·
            disponibilidad &lt; 60% · consistencia &lt; 0.3 · sin historial (1 temporada).
          </li>
        </ul>
        <p>
          <b className="text-emerald-300">strong_buy</b>: ≥ 3 positivas y 0 negativas ·{" "}
          <b className="text-emerald-300">buy</b>: ≥ 2 positivas y ≤ 1 negativa ·{" "}
          <b className="text-red-300">avoid</b>: ≥ 2 negativas · <b>hold</b>: el resto.
        </p>
      </Section>

      <Section
        title="4 · Valor posicional (pestaña «Avanzado»)"
        subtitle="PAR, tiers y escasez"
      >
        <Metric name="PAR (Points Above Replacement)">
          Puntos totales por encima del nivel de reemplazo de la posición (versión
          histórica de VORP).
        </Metric>
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
          <b className="text-vpv-text">VORP</b> hace comparables las posiciones,{" "}
          <b className="text-vpv-text">PtsRes</b> proyecta el resto de temporada, y{" "}
          <b className="text-vpv-text">Fiabilidad</b> separa el punto repetible del punto
          por nota. El equipo de cada jornada queda anclado en el histórico, así que los
          traspasos a mitad de temporada no reescriben el pasado.
        </p>
      </Section>
    </div>
  );
}
