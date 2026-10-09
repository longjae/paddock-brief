import { notFound } from "next/navigation";
import { Dashboard, type InterviewSection } from "@/components/dashboard";

const INTERVIEW_VIEWS = new Set<InterviewSection>(["press", "teams", "drivers", "videos", "media"]);

export default async function InterviewViewPage({ params }: { params: Promise<{ view: string }> }) {
  const { view } = await params;
  if (!INTERVIEW_VIEWS.has(view as InterviewSection)) notFound();
  return <Dashboard initialSection="interviews" initialInterviewSection={view as InterviewSection} />;
}
