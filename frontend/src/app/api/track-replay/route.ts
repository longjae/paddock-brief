type Session = { session_key: number; session_name: string; date_start: string; date_end?: string };
type Lap = { lap_number: number; date_start: string; lap_duration: number | null };
type Result = { driver_number: number; position: number | null };
type Location = { driver_number: number; date: string; x: number; y: number };
type CarData = { date: string; speed: number; rpm: number; n_gear: number; throttle: number; brake: number; drs: number | null };
type Driver = { driver_number: number; name_acronym: string; team_colour: string; team_name: string };
type Pit = { date: string; driver_number: number; lap_number: number; stop_duration: number | null };
type RaceControl = { date: string; category: string; flag: string | null; message: string };

const OPENF1 = "https://api.openf1.org/v1";
const FRAME_SECONDS = 2;

async function openF1<T>(path: string, params: URLSearchParams): Promise<T> {
  for (let attempt = 0; attempt < 3; attempt++) {
    const response = await fetch(`${OPENF1}/${path}?${params}`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(20000),
    }).catch(() => null);
    if (response?.ok) return response.json() as Promise<T>;
    if (response && response.status < 500 && response.status !== 429) throw new Error(`OpenF1 ${response.status}`);
    if (attempt === 2) throw new Error(`OpenF1 ${response?.status ?? "connection failed"}`);
    await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
  }
  throw new Error("OpenF1 unavailable");
}

export async function GET(request: Request) {
  const query = new URL(request.url).searchParams;
  const season = Number(query.get("season"));
  const country = query.get("country")?.trim() ?? "";
  const raceStart = query.get("raceStart") ?? "";
  const shortName = query.get("session") ?? "R";
  const sessionNames: Record<string, string[]> = { FP1: ["Practice 1"], FP2: ["Practice 2"], FP3: ["Practice 3"], SQ: ["Sprint Qualifying", "Sprint Shootout"], S: ["Sprint"], Q: ["Qualifying"], R: ["Race"] };
  const lapNumber = Number(query.get("lap") ?? "1");
  const selectedDriver = Number(query.get("driver") ?? "0");
  if (!sessionNames[shortName] || !Number.isInteger(season) || season < 2023 || season > new Date().getUTCFullYear() ||
      !/^[a-zA-Z .'-]{2,50}$/.test(country) || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(raceStart) ||
      !Number.isInteger(lapNumber) || lapNumber < 1 || lapNumber > 100 ||
      !Number.isInteger(selectedDriver) || selectedDriver < 0 || selectedDriver > 99) {
    return Response.json({ error: "Invalid replay request" }, { status: 400 });
  }

  try {
    const sessions = await openF1<Session[]>("sessions", new URLSearchParams({ year: String(season), country_name: country }));
    const expectedStart = new Date(`${raceStart.replace(" ", "T")}:00+09:00`).getTime();
    const session = sessions.filter((item) => sessionNames[shortName].includes(item.session_name) && item.date_end && new Date(item.date_end).getTime() < Date.now())
      .sort((a, b) => Math.abs(new Date(a.date_start).getTime() - expectedStart) - Math.abs(new Date(b.date_start).getTime() - expectedStart))[0];
    if (session && Math.abs(new Date(session.date_start).getTime() - expectedStart) > 24 * 60 * 60_000) {
      return Response.json({ available: false, reason: "선택한 GP의 위치 기록을 찾지 못했습니다." });
    }
    if (!session) return Response.json({ available: false, reason: "선택한 세션의 종료된 위치 기록이 없습니다." });

    const key = String(session.session_key);
    const [results, drivers] = await Promise.all([
      openF1<Result[]>("session_result", new URLSearchParams({ session_key: key })),
      openF1<Driver[]>("drivers", new URLSearchParams({ session_key: key })),
    ]);
    const sortedResults = [...results].sort((a, b) => (a.position ?? 999) - (b.position ?? 999));
    const leaderNumber = sortedResults.find((result) => result.position === 1)?.driver_number;
    if (!leaderNumber) return Response.json({ available: false, reason: "선택한 세션의 최종 순위가 아직 없습니다." });
    const focusNumber = sortedResults.some((result) => result.driver_number === selectedDriver) ? selectedDriver : leaderNumber;
    const referenceNumber = ["R", "S"].includes(shortName) ? leaderNumber : focusNumber;
    const laps = (await openF1<Lap[]>("laps", new URLSearchParams({ session_key: key, driver_number: String(referenceNumber) })))
      .filter((lap) => Number.isInteger(lap.lap_number) && lap.date_start).sort((a, b) => a.lap_number - b.lap_number);
    const selectedLap = laps.find((lap) => lap.lap_number === lapNumber) ?? (lapNumber === 1 ? laps[0] : undefined);
    if (!selectedLap) return Response.json({ available: false, reason: "선택한 랩의 위치 기록이 없습니다.", maxLap: laps.at(-1)?.lap_number ?? 0 });
    const nextLap = laps.find((lap) => lap.lap_number === selectedLap.lap_number + 1);
    const start = new Date(selectedLap.date_start).getTime();
    const naturalEnd = nextLap ? new Date(nextLap.date_start).getTime() : start + (selectedLap.lap_duration ?? 120) * 1000;
    const end = Math.min(start + 5 * 60_000, naturalEnd);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      return Response.json({ available: false, reason: "선택한 랩의 시각 정보가 없습니다." });
    }
    const windowParams = new URLSearchParams({ session_key: key, "date>": new Date(start).toISOString(), "date<": new Date(end).toISOString() });
    const [locationRows, carRows, pitRows, controlRows] = await Promise.all([
      openF1<Location[]>("location", windowParams),
      openF1<CarData[]>("car_data", new URLSearchParams({ ...Object.fromEntries(windowParams), driver_number: String(focusNumber) })),
      openF1<Pit[]>("pit", windowParams).catch(() => []),
      openF1<RaceControl[]>("race_control", windowParams).catch(() => []),
    ]);
    const orderedLocations = locationRows.filter((row) => Number.isFinite(row.x) && Number.isFinite(row.y) && Number.isFinite(new Date(row.date).getTime()))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    if (!orderedLocations.length) return Response.json({ available: false, reason: "선택한 랩의 위치 기록이 부족합니다." });
    const driverByNumber = new Map(drivers.map((driver) => [driver.driver_number, driver]));
    const rankByNumber = new Map(sortedResults.map((result, index) => [result.driver_number, result.position ?? index + 1]));
    const trace = orderedLocations.filter((row) => row.driver_number === referenceNumber).filter((_, index) => index % 5 === 0)
      .map(({ x, y }) => ({ x, y }));
    const latest = new Map<number, Location>();
    const frames = [];
    let locationIndex = 0;
    let carIndex = 0;
    let latestCar: CarData | null = null;
    const orderedCars = carRows.filter((row) => Number.isFinite(new Date(row.date).getTime()))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    for (let time = start; time < end; time += FRAME_SECONDS * 1000) {
      const sampleEnd = Math.min(time + FRAME_SECONDS * 1000, end);
      while (locationIndex < orderedLocations.length && new Date(orderedLocations[locationIndex].date).getTime() < sampleEnd) {
        const row = orderedLocations[locationIndex++];
        latest.set(row.driver_number, row);
      }
      while (carIndex < orderedCars.length && new Date(orderedCars[carIndex].date).getTime() < sampleEnd) latestCar = orderedCars[carIndex++];
      const positions = [...latest.values()].sort((a, b) => (rankByNumber.get(a.driver_number) ?? 999) - (rankByNumber.get(b.driver_number) ?? 999))
        .map((row) => ({ number: row.driver_number, x: row.x, y: row.y }));
      if (positions.length) frames.push({ time: new Date(time).toISOString(), positions,
        car: latestCar ? { speed: latestCar.speed, rpm: latestCar.rpm, gear: latestCar.n_gear, throttle: latestCar.throttle, brake: latestCar.brake, drs: latestCar.drs } : null });
    }
    const standings = sortedResults.map((result, index) => {
      const driver = driverByNumber.get(result.driver_number);
      return { number: result.driver_number, position: result.position ?? index + 1,
        code: driver?.name_acronym || `#${result.driver_number}`, team: driver?.team_name || "",
        colour: `#${driver?.team_colour || "e10600"}` };
    });
    const events = [
      ...pitRows.filter((row) => row.date && row.driver_number).map((row) => ({
        time: row.date, kind: "pit", label: `PIT · ${driverByNumber.get(row.driver_number)?.name_acronym || `#${row.driver_number}`}${row.stop_duration ? ` · ${row.stop_duration.toFixed(1)}초` : ""}`,
      })),
      ...controlRows.filter((row) => row.date && (row.category === "Flag" || row.category === "SafetyCar")).map((row) => ({
        time: row.date, kind: "control", label: row.flag ? `${row.flag} · ${row.message}` : row.message,
      })),
    ].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
    return Response.json({ available: true, sessionKey: session.session_key, lap: selectedLap.lap_number, maxLap: laps.at(-1)?.lap_number ?? selectedLap.lap_number,
      leaderNumber, focusNumber, frameSeconds: FRAME_SECONDS, frames, trace, standings, events });
  } catch (error) {
    console.error("OpenF1 track replay failed", error);
    return Response.json({ available: false, reason: "위치 기록을 불러오지 못했습니다." }, { status: 502 });
  }
}
