"use client";

import { useState } from "react";

const STATIC_BASE_URL =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api").replace(
    /\/api$/,
    "",
  );

function getPhotoUrl(photoPath: string): string {
  return `${STATIC_BASE_URL}/static/${photoPath}`;
}

export function PlayerAvatar({
  photoPath,
  name,
  size = 48,
}: {
  photoPath: string | null;
  name: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);

  if (!photoPath || failed) {
    // Fallback: initials circle
    const initials = name
      .split(" ")
      .map((w) => w[0])
      .slice(0, 2)
      .join("")
      .toUpperCase();
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center rounded-full bg-vpv-border text-[10px] font-bold text-vpv-text-muted"
        style={{ width: size, height: size }}
      >
        {initials}
      </span>
    );
  }

  return (
    <img
      src={getPhotoUrl(photoPath)}
      alt={name}
      width={size}
      height={size}
      className="shrink-0 rounded-full object-cover"
      style={{ width: size, height: size }}
      onError={() => setFailed(true)}
      loading="lazy"
    />
  );
}
