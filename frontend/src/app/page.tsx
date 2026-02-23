export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-vpv-bg">
      <div className="rounded-lg border border-vpv-card-border bg-vpv-card p-8 shadow-sm">
        <h1 className="text-3xl font-bold text-vpv-text">Liga VPV Fantasy</h1>
        <p className="mt-2 text-vpv-text-muted">v0.1.0 — En construcción</p>
        <div className="mt-4 flex gap-2">
          <span className="inline-flex items-center rounded-full bg-vpv-success px-2.5 py-0.5 text-xs font-medium text-white">
            Frontend OK
          </span>
        </div>
      </div>
    </main>
  );
}
