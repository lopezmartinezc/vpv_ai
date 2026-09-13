const LABELS: Record<string, string> = {
  standings: "la clasificación",
  current_matchday: "la jornada",
  copa: "la Copa",
  economy: "la economía",
};

/**
 * Names the parts of the home the server could not load (IN-02), so an empty
 * block is never taken for "there is no data".
 */
export function UnavailableNotice({
  sections,
  onRetry,
}: {
  sections: string[];
  onRetry: () => void;
}) {
  if (sections.length === 0) return null;
  const names = new Intl.ListFormat("es", { type: "conjunction" }).format(
    sections.map((section) => LABELS[section] ?? section),
  );
  return (
    <div role="alert" className="rounded-lg border border-vpv-danger p-4 text-sm text-vpv-text">
      No se pudo cargar {names}.{" "}
      <button type="button" onClick={onRetry} className="min-h-11 text-vpv-accent">
        Reintentar
      </button>
    </div>
  );
}
