const TYRE_NAMES = new Set(["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]);

export function tyreImagePath(compound: string): string {
  const name = compound.toUpperCase();
  return `/assets/tyres/${TYRE_NAMES.has(name) ? name.toLowerCase() : "unknown"}.svg`;
}
