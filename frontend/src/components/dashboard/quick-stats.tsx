interface QuickStatsProps {
  totalPlayed: number;
  totalParticipants: number;
  leaderName: string | null;
  leaderPoints: number | null;
}

export function QuickStats({
  totalPlayed,
  totalParticipants,
  leaderName,
  leaderPoints,
}: QuickStatsProps) {
  const stats = [
    { label: "Jornadas jugadas", value: totalPlayed },
    { label: "Participantes", value: totalParticipants },
    {
      label: "Lider",
      value: leaderName
        ? `${leaderName} (${leaderPoints})`
        : "–",
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-lg border border-vpv-card-border bg-vpv-card p-3 text-center"
        >
          <p className="text-lg font-bold text-vpv-text">{stat.value}</p>
          <p className="text-[11px] text-vpv-text-muted">{stat.label}</p>
        </div>
      ))}
    </div>
  );
}
