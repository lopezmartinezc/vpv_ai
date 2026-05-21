/**
 * Mapping team name (as scraped from futbolfantasy.com) to ISO 3166-1 alpha-2
 * country code. Used by <CountryFlag> to render national flags in tournament
 * pages.
 *
 * Add new entries here when a new country qualifies. Comparisons are
 * case-insensitive and trim whitespace; both the original Spanish name and
 * common variants are accepted.
 */
const COUNTRY_FLAG_MAP: Record<string, string> = {
  // Anfitriones
  "estados unidos": "us",
  "eeuu": "us",
  "usa": "us",
  "mexico": "mx",
  "méxico": "mx",
  "canada": "ca",
  "canadá": "ca",

  // CONMEBOL
  "argentina": "ar",
  "brasil": "br",
  "uruguay": "uy",
  "colombia": "co",
  "ecuador": "ec",
  "paraguay": "py",
  "bolivia": "bo",
  "peru": "pe",
  "perú": "pe",
  "chile": "cl",
  "venezuela": "ve",

  // UEFA
  "alemania": "de",
  "francia": "fr",
  "españa": "es",
  "espana": "es",
  "portugal": "pt",
  "holanda": "nl",
  "paises bajos": "nl",
  "países bajos": "nl",
  "belgica": "be",
  "bélgica": "be",
  "italia": "it",
  "inglaterra": "gb-eng",
  "england": "gb-eng",
  "escocia": "gb-sct",
  "gales": "gb-wls",
  "irlanda del norte": "gb-nir",
  "suiza": "ch",
  "croacia": "hr",
  "polonia": "pl",
  "austria": "at",
  "noruega": "no",
  "suecia": "se",
  "dinamarca": "dk",
  "finlandia": "fi",
  "islandia": "is",
  "republica checa": "cz",
  "república checa": "cz",
  "rep checa": "cz",
  "chequia": "cz",
  "czechia": "cz",
  "eslovaquia": "sk",
  "eslovenia": "si",
  "hungria": "hu",
  "hungría": "hu",
  "rumania": "ro",
  "rumanía": "ro",
  "bulgaria": "bg",
  "grecia": "gr",
  "turquia": "tr",
  "turquía": "tr",
  "serbia": "rs",
  "ucrania": "ua",
  "rusia": "ru",
  "irlanda": "ie",
  "bosnia": "ba",
  "bosnia y herzegovina": "ba",
  "bosnia y hercegovina": "ba",
  "bosnia herzegovina": "ba",
  "bosnia hercegovina": "ba",
  "bosnia i herzegovina": "ba",
  "albania": "al",
  "macedonia del norte": "mk",
  "georgia": "ge",
  "armenia": "am",
  "azerbaiyan": "az",
  "azerbaiyán": "az",
  "kazajistan": "kz",
  "kazajistán": "kz",
  "kazajstán": "kz",

  // AFC
  "japon": "jp",
  "japón": "jp",
  "corea del sur": "kr",
  "corea": "kr",
  "iran": "ir",
  "irán": "ir",
  "iraq": "iq",
  "irak": "iq",
  "australia": "au",
  "arabia saudi": "sa",
  "arabia saudí": "sa",
  "arabia saudita": "sa",
  "uzbekistan": "uz",
  "uzbekistán": "uz",
  "jordania": "jo",
  "qatar": "qa",
  "catar": "qa",
  "emiratos arabes unidos": "ae",
  "emiratos árabes unidos": "ae",
  "kuwait": "kw",
  "siria": "sy",
  "tailandia": "th",
  "vietnam": "vn",
  "indonesia": "id",
  "malasia": "my",
  "filipinas": "ph",
  "india": "in",
  "china": "cn",

  // CONCACAF
  "panama": "pa",
  "panamá": "pa",
  "curazao": "cw",
  "curaçao": "cw",
  "haiti": "ht",
  "haití": "ht",
  "costa rica": "cr",
  "honduras": "hn",
  "jamaica": "jm",
  "el salvador": "sv",
  "guatemala": "gt",
  "trinidad y tobago": "tt",

  // OFC
  "nueva zelanda": "nz",

  // CAF
  "marruecos": "ma",
  "tunez": "tn",
  "túnez": "tn",
  "egipto": "eg",
  "ghana": "gh",
  "senegal": "sn",
  "costa de marfil": "ci",
  "sudafrica": "za",
  "sudáfrica": "za",
  "argelia": "dz",
  "cabo verde": "cv",
  "nigeria": "ng",
  "camerun": "cm",
  "camerún": "cm",
  "mali": "ml",
  "malí": "ml",
  "burkina faso": "bf",
  "rd congo": "cd",
  "r d congo": "cd",
  "rdc": "cd",
  "republica democratica del congo": "cd",
  "rep democratica del congo": "cd",
  "rep dem del congo": "cd",
  "rep dem congo": "cd",
  "congo rd": "cd",
  "congo kinshasa": "cd",
  "rep del congo": "cg",
  "republica del congo": "cg",
  "congo brazzaville": "cg",
  "congo": "cg",
  "zambia": "zm",
  "angola": "ao",
  "kenya": "ke",
  "kenia": "ke",
  "guinea": "gn",
  "uganda": "ug",
  "etiopia": "et",
  "etiopía": "et",
};

const SLUG_FLAG_MAP: Record<string, string> = {
  "corea-del-sur": "kr",
  "estados-unidos": "us",
  "arabia-saudi": "sa",
  "arabia-saudita": "sa",
  "nueva-zelanda": "nz",
  "cabo-verde": "cv",
  "costa-de-marfil": "ci",
  "republica-checa": "cz",
  "rep-checa": "cz",
  "paises-bajos": "nl",
  "macedonia-del-norte": "mk",
  "irlanda-del-norte": "gb-nir",
  "bosnia-y-herzegovina": "ba",
  "bosnia-y-hercegovina": "ba",
  "bosnia-herzegovina": "ba",
  "emiratos-arabes-unidos": "ae",
  "trinidad-y-tobago": "tt",
  "el-salvador": "sv",
  "costa-rica": "cr",
  "rd-congo": "cd",
  "rdc": "cd",
  "republica-democratica-del-congo": "cd",
  "congo-kinshasa": "cd",
  "rep-del-congo": "cg",
  "congo-brazzaville": "cg",
};

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // strip combining accents
    .toLowerCase()
    .replace(/\./g, "") // "Rep." -> "Rep"
    .replace(/[-_]/g, " ") // "Bosnia-Herzegovina" -> "Bosnia Herzegovina"
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Resolve an ISO 3166-1 alpha-2 country code from a team's name and slug.
 * Returns `null` when the team is not in the mapping (e.g. La Liga clubs).
 */
export function resolveCountryCode(
  teamName?: string | null,
  slug?: string | null,
): string | null {
  if (slug) {
    const slugKey = slug.toLowerCase().trim();
    if (SLUG_FLAG_MAP[slugKey]) return SLUG_FLAG_MAP[slugKey];
  }
  if (teamName) {
    const normName = normalize(teamName);
    if (COUNTRY_FLAG_MAP[normName]) return COUNTRY_FLAG_MAP[normName];
  }
  return null;
}
