"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { CountryFlag } from "@/components/ui/country-flag";

interface SortableTeamCardProps {
  id: string;
  teamName: string;
  shortName?: string | null;
  logoPath?: string | null;
  ordinal?: string | null;
  disabled?: boolean;
  size?: "sm" | "md";
  rightSlot?: React.ReactNode;
}

/**
 * Draggable card for a team in tournament predictions (groups, best thirds,
 * bracket). The id must be unique within a SortableContext.
 */
export function SortableTeamCard({
  id,
  teamName,
  shortName,
  logoPath,
  ordinal,
  disabled,
  size = "md",
  rightSlot,
}: SortableTeamCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id, disabled });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
    touchAction: "none",
  };

  const isSmall = size === "sm";

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 rounded-md border border-vpv-border bg-vpv-bg px-2 py-1.5 select-none ${
        disabled ? "opacity-60" : "cursor-grab active:cursor-grabbing hover:border-vpv-accent/40"
      } ${isSmall ? "text-xs" : "text-sm"}`}
      {...attributes}
      {...listeners}
    >
      <span
        aria-hidden="true"
        className="shrink-0 text-vpv-text-muted/60"
        title="Arrastra para reordenar"
      >
        {/* drag handle icon (Unicode bars) */}
        ⋮⋮
      </span>
      {ordinal && (
        <span className="w-6 shrink-0 font-semibold text-vpv-text-muted">{ordinal}</span>
      )}
      <CountryFlag
        teamName={teamName}
        fallbackLogo={logoPath}
        size={isSmall ? 16 : 20}
      />
      <span className="min-w-0 flex-1 truncate text-vpv-text">{shortName ?? teamName}</span>
      {rightSlot}
    </div>
  );
}
