// The Liga's playoffs carry David Silva's name, in his memory. Tournaments keep
// the plain "Playoffs".
export const LIGA_PLAYOFF_LABEL = "Playoff DS";
export const LIGA_PLAYOFF_TITLE = "PLAYOFF DAVID SILVA";

/** Banner at the top of the Liga's playoff page: his name. */
export function PlayoffDsHero({ subtitle }: { subtitle?: string }) {
  return (
    <div className="rounded-2xl border border-orange-500/40 bg-[#0d0d0d] px-5 py-5 sm:px-7">
      <h1 className="text-2xl font-extrabold uppercase leading-tight tracking-wide text-orange-500 sm:text-4xl">
        {LIGA_PLAYOFF_TITLE}
      </h1>
      {subtitle && <p className="mt-1 text-sm text-orange-200/80">{subtitle}</p>}
    </div>
  );
}
