import { notFound, redirect } from "next/navigation";
import { Dashboard, type MainSection } from "@/components/dashboard";

const MAIN_SECTIONS = new Set<MainSection>(["weekend", "interviews", "championship", "live", "glossary"]);

export default async function RaceSectionPage({ params }: { params: Promise<{ slug: string; section: string }> }) {
  const { slug, section } = await params;
  if (section === "race-centre") redirect(`/races/${slug}/weekend`);
  if (!MAIN_SECTIONS.has(section as MainSection)) notFound();
  return <Dashboard initialEventSlug={slug} initialSection={section as MainSection} />;
}
