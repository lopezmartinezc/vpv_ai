import { redirect } from "next/navigation";

export default function BurgerRankingRedirect() {
  // Legacy path. The page now lives at /ranking with two tabs
  // (Burger + Banquillazo); any bookmark or old link bounces here.
  redirect("/ranking");
}
