// Date helpers. The API sends calendar dates as "YYYY-MM-DD" and moments in
// time as ISO strings with a timezone. They need different handling:
// `new Date("2026-11-30")` is midnight UTC, which shows as 29 Nov west of UTC.

const dateFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });
const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

/** A calendar date ("2026-11-30") as a local Date at midnight. */
export function parseCalendarDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function formatDate(value: string | null | undefined): string {
  return value ? dateFormat.format(parseCalendarDate(value)) : "—";
}

/** The calendar day of a timestamp in the viewer's timezone (slicing the ISO
 *  string would give the UTC day, which is off by one near midnight). */
export function formatDayOf(timestamp: string): string {
  return dateFormat.format(new Date(timestamp));
}

export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTimeFormat.format(new Date(value)) : "—";
}

/** Whole days from today to a calendar date: 0 today, negative if past. */
export function daysUntil(value: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((parseCalendarDate(value).getTime() - today.getTime()) / 86_400_000);
}

export function describeDaysUntil(days: number): string {
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days === -1) return "yesterday";
  return days > 0 ? `in ${days} days` : `${-days} days ago`;
}

/** ISO moment → value for <input type="datetime-local"> in the browser's timezone. */
export function toDateTimeLocal(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

/** <input type="datetime-local"> value (browser's timezone) → ISO string in UTC. */
export function fromDateTimeLocal(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}
