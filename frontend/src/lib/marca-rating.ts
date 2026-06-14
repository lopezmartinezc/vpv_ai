/**
 * Marca rating display helpers.
 *
 * The DB and API exchange numeric strings ("1"…"4", "SC", "-")
 * — see `MarcaRatingValue` in `@/types`. The UI shows ★/★★/… for
 * the four star levels and the raw marker for "SC" / "-".
 */

export function starsForRating(rating: string | null | undefined): string {
  switch (rating) {
    case "1":
      return "★";
    case "2":
      return "★★";
    case "3":
      return "★★★";
    case "4":
      return "★★★★";
    default:
      return rating ?? "";
  }
}
