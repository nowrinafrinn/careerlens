import type { RecruitmentEvent } from "@/lib/applications";
import { formatDate, formatDateTime } from "@/lib/format";
import { APPLICATION_STATUS, ROUND_RESULT, ROUND_STATUS, ROUND_TYPE } from "@/lib/labels";

type Values = Record<string, unknown> | null;

const FIELD_LABELS: Record<string, string> = {
  deadline: "Deadline",
  applied_on: "Applied date",
  follow_up_date: "Follow-up date",
  confirmation_deadline: "Confirmation deadline",
};

const asString = (value: unknown) => (typeof value === "string" ? value : null);

function label(map: Record<string, { label: string } | string>, value: unknown): string {
  const key = asString(value);
  if (!key) return "—";
  const entry = map[key];
  return typeof entry === "string" ? entry : (entry?.label ?? key);
}

function formatValue(field: string, value: unknown): string {
  const text = asString(value);
  if (!text) return "not set";
  return field.endsWith("_at") || field === "confirmation_deadline" ? formatDateTime(text) : formatDate(text);
}

function describeDateChanges(old: Values, next: Values): string[] {
  return Object.keys(next ?? {})
    .filter((field) => field !== "round_name")
    .map((field) => {
      const name = FIELD_LABELS[field] ?? field;
      const before = old?.[field];
      const after = next?.[field];
      if (!before) return `${name} set to ${formatValue(field, after)}`;
      if (!after) return `${name} cleared (was ${formatValue(field, before)})`;
      return `${name} changed from ${formatValue(field, before)} to ${formatValue(field, after)}`;
    });
}

/** One or more plain-language lines describing what an event recorded. */
export function describeEvent(event: RecruitmentEvent): string[] {
  const old = event.old_value as Values;
  const next = event.new_value as Values;
  const round = asString(next?.round_name) ?? asString(old?.round_name) ?? "Round";

  switch (event.event_type) {
    case "application_created":
      return [`Application saved as ${label(APPLICATION_STATUS, next?.status)}`];
    case "application_status_changed":
      return [`Status changed from ${label(APPLICATION_STATUS, old?.status)} to ${label(APPLICATION_STATUS, next?.status)}`];
    case "application_date_changed":
    case "round_date_changed":
      return describeDateChanges(old, next).map((line) =>
        event.event_type === "round_date_changed" ? `${round}: ${line.charAt(0).toLowerCase()}${line.slice(1)}` : line,
      );
    case "application_cv_changed": {
      const before = asString(old?.cv_label);
      const after = asString(next?.cv_label);
      if (!before) return [`CV set to “${after}”`];
      if (!after) return [`CV removed (was “${before}”)`];
      return [`CV changed from “${before}” to “${after}”`];
    }
    case "application_archived":
      return ["Application archived"];
    case "application_restored":
      return ["Application restored from the archive"];
    case "round_created": {
      const when = asString(next?.scheduled_at);
      const type = label(ROUND_TYPE, next?.round_type);
      // "Online assessment (Online assessment)" says nothing twice; name the type only when it adds information.
      const typeNote = type.toLowerCase() === round.toLowerCase() ? "" : ` (${type})`;
      return [`Round added: ${round}${typeNote}${when ? `, ${formatDateTime(when)}` : ""}`];
    }
    case "round_scheduled":
      return [`${round} scheduled for ${formatValue("scheduled_at", next?.scheduled_at)}`];
    case "round_rescheduled":
      return [
        `${round} moved from ${formatValue("scheduled_at", old?.scheduled_at)} to ${formatValue("scheduled_at", next?.scheduled_at)}`,
      ];
    case "round_status_changed":
      return [`${round}: ${label(ROUND_STATUS, old?.status)} → ${label(ROUND_STATUS, next?.status)}`];
    case "round_result_recorded":
      return [`${round}: result ${label(ROUND_RESULT, old?.result).toLowerCase()} → ${label(ROUND_RESULT, next?.result).toLowerCase()}`];
    case "round_deleted":
      return [`Round deleted: ${round}`];
    default:
      return [String(event.event_type)];
  }
}

export function Timeline({ events }: { events: RecruitmentEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-muted-foreground">No history yet.</p>;
  }
  // Newest first: the most recent change is usually what you're looking for.
  const ordered = [...events].reverse();
  return (
    <ol className="relative flex flex-col gap-4 border-l pl-4">
      {ordered.map((event) => (
        <li key={event.id} className="relative">
          <span aria-hidden className="absolute top-1.5 -left-[21px] size-2.5 rounded-full border-2 border-background bg-muted-foreground/60" />
          <p className="text-xs text-muted-foreground tabular-nums">
            <time dateTime={event.occurred_at}>{formatDateTime(event.occurred_at)}</time>
          </p>
          {describeEvent(event).map((line, index) => (
            <p key={index} className="text-sm">
              {line}
            </p>
          ))}
          {event.reason && <p className="mt-0.5 text-sm text-muted-foreground">Reason: {event.reason}</p>}
        </li>
      ))}
    </ol>
  );
}
