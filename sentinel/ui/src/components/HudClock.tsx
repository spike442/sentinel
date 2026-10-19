import { useEffect, useState } from "react";

function utcClock(now: Date): string {
  return now.toISOString().slice(11, 19);
}

export function HudClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const clock = utcClock(now);
  return (
    <time className="hud-clock" dateTime={now.toISOString()}>
      <span>UTC</span> {clock}
    </time>
  );
}
