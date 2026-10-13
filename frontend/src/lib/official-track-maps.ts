type TrackSource = { f1Slug: string; imageName: string; fiaDocument?: string };

// The F1 images show the 2026 circuit layout, sectors, corners and speed trap.
// FIA circuit-map documents add the event's confirmed Straight Mode zones.
const TRACKS: Record<string, TrackSource> = {
  australian: { f1Slug: "australia", imageName: "melbourne", fiaDocument: "2026_australian_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_quarantine_zone.pdf" },
  chinese: { f1Slug: "china", imageName: "shanghai", fiaDocument: "2026_chinese_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_battery_containment_area_and_red_zone.pdf" },
  japanese: { f1Slug: "japan", imageName: "suzuka", fiaDocument: "2026_japanese_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_battery_containment_area_and_red_zone.pdf" },
  miami: { f1Slug: "miami", imageName: "miami", fiaDocument: "2026_miami_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf" },
  canadian: { f1Slug: "canada", imageName: "montreal", fiaDocument: "2026_canadian_grand_prix_-_competition_notes_-_circuit_map_v2.pdf" },
  monaco: { f1Slug: "monaco", imageName: "montecarlo", fiaDocument: "2026_monaco_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf" },
  barcelona: { f1Slug: "barcelona-catalunya", imageName: "catalunya", fiaDocument: "2026_barcelona-catalunya_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_and_emergency_exits_map.pdf" },
  austrian: { f1Slug: "austria", imageName: "spielberg", fiaDocument: "2026_austrian_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf" },
  british: { f1Slug: "great-britain", imageName: "silverstone", fiaDocument: "2026_british_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf" },
  belgian: { f1Slug: "belgium", imageName: "spafrancorchamps", fiaDocument: "2026_belgian_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf" },
  hungarian: { f1Slug: "hungary", imageName: "hungaroring", fiaDocument: "2026_hungarian_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf" },
  dutch: { f1Slug: "netherlands", imageName: "zandvoort", fiaDocument: "2026_dutch_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_and_emergency_exits_map.pdf" },
  italian: { f1Slug: "italy", imageName: "monza", fiaDocument: "2026_italian_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf" },
  spanish: { f1Slug: "spain", imageName: "madring", fiaDocument: "2026_spanish_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_and_emergency_exits_map.pdf" },
  azerbaijan: { f1Slug: "azerbaijan", imageName: "baku", fiaDocument: "2026_azerbaijan_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf" },
  bahrain: { f1Slug: "bahrain", imageName: "kualalumpur", fiaDocument: "2026_bahrain_grand_prix_in_malaysia_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf" },
  singapore: { f1Slug: "singapore", imageName: "singapore", fiaDocument: "2026_singapore_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_and_emergency_exits_map.pdf" },
  "united-states": { f1Slug: "united-states", imageName: "austin" },
  "mexico-city": { f1Slug: "mexico", imageName: "mexicocity" },
  brazilian: { f1Slug: "brazil", imageName: "interlagos" },
  "las-vegas": { f1Slug: "las-vegas", imageName: "lasvegas" },
  qatar: { f1Slug: "qatar", imageName: "lusail" },
  "abu-dhabi": { f1Slug: "united-arab-emirates", imageName: "yasmarinacircuit" },
};

export function officialTrackMap(eventSlug: string) {
  if (!eventSlug.startsWith("2026-")) return null;
  const track = TRACKS[eventSlug.slice(5)];
  if (!track) return null;
  return {
    imageUrl: `https://media.formula1.com/image/upload/c_fit,h_704/q_auto/v1740000001/common/f1/2026/track/2026track${track.imageName}detailed.webp`,
    sourceUrl: `https://www.formula1.com/en/racing/2026/${track.f1Slug}`,
    fiaDocumentUrl: track.fiaDocument ? `https://www.fia.com/system/files/decision-document/${track.fiaDocument}` : null,
    fiaMapImageUrl: track.fiaDocument ? `/tracks/fia-2026-${eventSlug.slice(5)}.jpg` : null,
  };
}
