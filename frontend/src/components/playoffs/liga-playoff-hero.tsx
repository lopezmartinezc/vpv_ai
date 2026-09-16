import { LIGA_PLAYOFF_NAME } from "@/lib/playoff-name";

/** Banner at the top of the Liga's playoff page: the cup's name. */
export function LigaPlayoffHero({ subtitle }: { subtitle?: string }) {
  return (
    <div className="rounded-2xl border border-orange-500/40 bg-[#0d0d0d] px-5 py-5 sm:px-7">
      <h1 className="text-2xl font-extrabold leading-tight tracking-wide text-orange-500 sm:text-4xl">
        {LIGA_PLAYOFF_NAME}
      </h1>
      {subtitle && <p className="mt-1 text-sm text-orange-200/80">{subtitle}</p>}
    </div>
  );
}
