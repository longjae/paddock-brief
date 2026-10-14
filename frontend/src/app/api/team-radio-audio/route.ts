const BASE = "https://livetiming.formula1.com/static";

export async function GET(request: Request) {
  const query = new URL(request.url).searchParams;
  const sessionPath = query.get("sessionPath") || "";
  const path = query.get("path") || "";
  if (!/^[A-Za-z0-9_/-]+\/$/.test(sessionPath) || sessionPath.includes("..") ||
      !/^TeamRadio\/[A-Za-z0-9_-]+\.mp3$/.test(path)) {
    return new Response("Invalid team radio path", { status: 400 });
  }
  try {
    const response = await fetch(`${BASE}/${sessionPath}${path}`, {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; PaddockBrief/1.0)" },
      signal: AbortSignal.timeout(15000),
      next: { revalidate: 86400 },
    });
    if (!response.ok) return new Response("Team radio audio unavailable", { status: 502 });
    return new Response(response.body, {
      headers: { "Content-Type": "audio/mpeg", "Cache-Control": "public, max-age=86400, s-maxage=86400" },
    });
  } catch {
    return new Response("Team radio audio unavailable", { status: 502 });
  }
}
