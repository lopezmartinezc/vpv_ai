"use client";

import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

export default function BackupPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleDownload() {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const token = localStorage.getItem("vpv_token");
      const res = await fetch(`${API_BASE_URL}/backup/admin/download`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.message || `Error ${res.status}`);
      }

      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || "ligavpv_backup.sql";

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setSuccess(`Backup descargado: ${filename}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error generando backup");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-vpv-card-border bg-vpv-card p-6">
        <h2 className="mb-2 text-lg font-semibold text-vpv-text">
          Backup de base de datos
        </h2>
        <p className="mb-4 text-sm text-vpv-text-muted">
          Genera y descarga un volcado completo de la base de datos PostgreSQL
          (pg_dump). El archivo incluye esquema y datos.
        </p>

        {error && (
          <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-3 text-sm text-green-400">
            {success}
          </div>
        )}

        <button
          onClick={handleDownload}
          disabled={loading}
          className="rounded-lg bg-vpv-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-vpv-accent/80 disabled:opacity-50"
        >
          {loading ? "Generando backup..." : "Descargar backup (.sql)"}
        </button>
      </section>
    </div>
  );
}
