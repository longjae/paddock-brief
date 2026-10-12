type Session = { session_key: number; session_name: string; date_start: string; date_end?: string };
type Location = { driver_number: number; date: string; x: number; y: number };
type CarData = { driver_number: number; date: string; speed: number; rpm: number; n_gear: number; throttle: number; brake: number; drs: number | null };
type Driver = { driver_number: number; name_acronym: string; team_colour: string; team_name: string };

const OPENF1 = "https://api.openf1.org/v1";

async function openF1<T>(path: string, params: URLSearchParams): Promise<T> {
  const response = await fetch(`${OPENF1}/${path}?${params}`, {
    next: { revalidate: 3600 },
    signal: AbortSignal.timeout(12000),
  });
  if (!response.ok) throw new Error(`OpenF1 ${response.status}`);
  return response.json() as Promise<T>;
}

export async function GET(request: Request) {
  const query = new URL(request.url).searchParams;
  const season = Number(query.get("season"));
  const country = query.get("country")?.trim() ?? "";
  const raceStart = query.get("raceStart") ?? "";
  const minute = Number(query.get("minute") ?? "10");
  const selectedDriver = Number(query.get("driver") ?? "0");
  if (!Number.isInteger(season) || season < 2023 || season > new Date().getUTCFullYear() ||
      !/^[a-zA-Z .'-]{2,50}$/.test(country) || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(raceStart) ||
      !Number.isInteger(minute) || minute < 5 || minute > 180 || !Number.isInteger(selectedDriver) || selectedDriver < 0 || selectedDriver > 99) {
    return Response.json({ error: "Invalid replay request" }, { status: 400 });
  }

  try {
    const sessions = await openF1<Session[]>("sessions", new URLSearchParams({ year: String(season), country_name: country }));
    const expectedStart = new Date(`${raceStart.replace(" ", "T")}:00+09:00`).getTime();
    const session = sessions.filter((item) => item.session_name === "Race" && item.date_end && new Date(item.date_end).getTime() < Date.now())
      .sort((a, b) => Math.abs(new Date(a.date_start).getTime() - expectedStart) - Math.abs(new Date(b.date_start).getTime() - expectedStart))[0];
    if (session && Math.abs(new Date(session.date_start).getTime() - expectedStart) > 24 * 60 * 60_000) {
      return Response.json({ available: false, reason: "선택한 GP의 위치 기록을 찾지 못했습니다." });
    }
    if (!session) return Response.json({ available: false, reason: "종료된 레이스 위치 기록이 없습니다." });

    const start = new Date(session.date_start).getTime();
    const traceStart = new Date(start + 5 * 60_000);
    const sampleStart = new Date(start + minute * 60_000);
    if (sampleStart.getTime() > new Date(session.date_end!).getTime()) {
      return Response.json({ available: false, reason: "선택한 시각이 레이스 종료 이후입니다." });
    }
    const windowParams = (from: Date, seconds: number) => new URLSearchParams({
      session_key: String(session.session_key),
      "date>": from.toISOString(),
      "date<": new Date(from.getTime() + seconds * 1000).toISOString(),
    });
    const [traceRows, positionRows, drivers] = await Promise.all([
      openF1<Location[]>("location", windowParams(traceStart, 120)),
      openF1<Location[]>("location", windowParams(sampleStart, 3)),
      openF1<Driver[]>("drivers", new URLSearchParams({ session_key: String(session.session_key) })),
    ]);
    const byDriver = new Map<number, Location>();
    for (const row of positionRows) if (Number.isFinite(row.x) && Number.isFinite(row.y)) byDriver.set(row.driver_number, row);
    const traceCounts = new Map<number, number>();
    for (const row of traceRows) if (Number.isFinite(row.x) && Number.isFinite(row.y)) traceCounts.set(row.driver_number, (traceCounts.get(row.driver_number) ?? 0) + 1);
    const traceDriver = [...traceCounts].sort((a, b) => b[1] - a[1])[0]?.[0];
    const trace = traceRows.filter((row) => row.driver_number === traceDriver).filter((_, index) => index % 4 === 0).map(({ x, y }) => ({ x, y }));
    if (trace.length < 20 || byDriver.size === 0) return Response.json({ available: false, reason: "해당 시각의 위치 기록이 부족합니다." });
    const focusNumber = byDriver.has(selectedDriver) ? selectedDriver : byDriver.keys().next().value as number;
    const carRows = await openF1<CarData[]>("car_data", new URLSearchParams({
      ...Object.fromEntries(windowParams(sampleStart, 2)), driver_number: String(focusNumber),
    }));
    const locationTime = new Date(byDriver.get(focusNumber)!.date).getTime();
    const car = carRows.filter((row) => row.driver_number === focusNumber)
      .sort((a, b) => Math.abs(new Date(a.date).getTime() - locationTime) - Math.abs(new Date(b.date).getTime() - locationTime))[0] ?? null;
    const driverByNumber = new Map(drivers.map((driver) => [driver.driver_number, driver]));
    return Response.json({ available: true, sessionKey: session.session_key, sessionTime: sampleStart.toISOString(),
      trace, focusNumber, car: car ? { speed: car.speed, rpm: car.rpm, gear: car.n_gear, throttle: car.throttle, brake: car.brake, drs: car.drs } : null,
      positions: [...byDriver.values()].map(({ driver_number, x, y }) => ({ number: driver_number, x, y,
        code: driverByNumber.get(driver_number)?.name_acronym || `#${driver_number}`,
        team: driverByNumber.get(driver_number)?.team_name || "",
        colour: `#${driverByNumber.get(driver_number)?.team_colour || "e10600"}`,
      })) });
  } catch {
    return Response.json({ available: false, reason: "위치 기록을 불러오지 못했습니다." }, { status: 502 });
  }
}
