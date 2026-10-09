import { notFound } from "next/navigation";
import { Dashboard, type MainSection } from "@/components/dashboard";

const MAIN_SECTIONS = new Set<MainSection>(["weekend", "interviews", "championship", "race-centre", "glossary"]);

export default async function RaceSectionPage({ params }: { params: Promise<{ slug: string; section: string }> }) {
  const { slug, section } = await params;
  if (!MAIN_SECTIONS.has(section as MainSection)) notFound();
  return <Dashboard initialEventSlug={slug} initialSection={section as MainSection} />;
}
