import { notFound } from "next/navigation";
import { Dashboard, type InterviewSection } from "@/components/dashboard";

const INTERVIEW_VIEWS = new Set<InterviewSection>(["press", "teams", "drivers", "videos", "media"]);

export default async function RaceInterviewPage({ params }: { params: Promise<{ slug: string; view: string }> }) {
  const { slug, view } = await params;
  if (!INTERVIEW_VIEWS.has(view as InterviewSection)) notFound();
  return <Dashboard initialEventSlug={slug} initialSection="interviews" initialInterviewSection={view as InterviewSection} />;
}
