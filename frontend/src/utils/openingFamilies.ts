const FAMILY_PREFIXES = [
  "Nimzo-Indian Defense",
  "Queen's Gambit Accepted",
  "Queen's Gambit Declined",
  "King's Indian Defense",
  "Queen's Indian Defense",
  "Bogo-Indian Defense",
  "Caro-Kann Defense",
  "Sicilian Defense",
  "French Defense",
  "Italian Game",
  "Ruy Lopez",
  "English Opening",
  "Scandinavian Defense",
  "Alekhine Defense",
  "Modern Defense",
  "Pirc Defense",
  "Philidor Defense",
  "Petrov's Defense",
  "Ponziani Opening",
  "Scotch Game",
  "Four Knights Game",
  "Vienna Game",
  "Bishop's Opening",
  "King's Gambit",
  "Center Game",
  "Queen's Pawn Game",
  "London System",
  "Trompowsky Attack",
  "Dutch Defense",
  "Polish Opening",
  "Nimzowitsch-Larsen Attack",
  "Bird Opening",
  "Reti Opening",
  "Semi-Slav Defense",
  "Grunfeld Defense",
  "Blumenfeld Countergambit",
];

const FAMILY_ALIASES: Array<[string, string]> = [
  ["Kings Pawn Opening", "King's Pawn Game"],
  ["King Pawn Opening", "King's Pawn Game"],
  ["Closed Sicilian Defense", "Sicilian Defense"],
  ["Open Sicilian Defense", "Sicilian Defense"],
  ["Sicilian Defence", "Sicilian Defense"],
  ["Closed Sicilian Defence", "Sicilian Defense"],
];

export function openingFamily(openingName: string | null | undefined, fallback?: string | null): string {
  const name = normalize(openingName || fallback || "");
  if (!name) return "Unknown";

  const beforeDelimiter = normalize(name.split(/[:,]/, 1)[0]);
  return matchFamily(beforeDelimiter || name);
}

function matchFamily(name: string) {
  const compactName = compact(name);

  for (const [alias, family] of FAMILY_ALIASES) {
    const compactAlias = compact(alias);
    if (compactName === compactAlias || compactName.startsWith(`${compactAlias} `)) return family;
  }

  for (const family of FAMILY_PREFIXES) {
    const compactFamily = compact(family);
    if (compactName === compactFamily || compactName.startsWith(`${compactFamily} `)) return family;
  }

  return name;
}

function normalize(value: string) {
  return value.replace(/;/g, ",").replace(/\s+/g, " ").trim();
}

function compact(value: string) {
  return value
    .toLowerCase()
    .replace(/'/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
