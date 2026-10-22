import type { Session } from "./types";

export function isBeforeFirstSession(sessions: Session[], now: number, hasLiveFeed = false): boolean {
  if (hasLiveFeed || sessions.some((session) => session.status === "live" || session.status === "done")) return false;
  const starts = sessions.map((session) => Date.parse(`${session.startsAt.replace(" ", "T")}:00+09:00`)).filter(Number.isFinite);
  return starts.length > 0 && now < Math.min(...starts);
}
