import Link from "next/link";

import { ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button-class";

/** Shown when a page's main record can't be loaded: "not found" for a 404, a
 *  connection hint for anything else, and always a way back. */
export function LoadError({
  error,
  thing,
  backHref,
  backLabel,
}: {
  error: unknown;
  thing: string; // "Journal", "Skill gap"…
  backHref: string;
  backLabel: string;
}) {
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <div role="alert" className="flex flex-col items-start gap-3">
      <h1 className="text-xl font-semibold">{notFound ? `${thing} not found` : `This ${thing.toLowerCase()} couldn't be loaded`}</h1>
      <p className="text-sm text-muted-foreground">
        {notFound
          ? "It may have been deleted, or the link is wrong."
          : "Check your connection and that the backend is running, then refresh the page."}
      </p>
      <Link href={backHref} className={buttonClass({ variant: "outline", size: "sm" })}>
        {backLabel}
      </Link>
    </div>
  );
}
