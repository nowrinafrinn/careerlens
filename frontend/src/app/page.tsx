import { SystemStatus } from "@/components/system-status";

// Milestone 1 placeholder home page. Replaced by the dashboard later; for now
// it proves the browser → Next.js → FastAPI → Postgres chain works.
export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-4 py-12 sm:py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight text-balance">CareerLens</h1>
        <p className="text-muted-foreground">
          Job requirements, CV evidence, preparation and recruitment records in one place.
          The workspace is being built; this page checks that every layer is connected.
        </p>
      </header>

      <SystemStatus />

      <p className="text-sm text-muted-foreground">
        API documentation:{" "}
        <a href="/api/docs" className="font-medium text-foreground underline underline-offset-4">
          /api/docs
        </a>
      </p>
    </main>
  );
}
