"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { aiKeys, getAIStatus, setAIConsent } from "@/lib/ai";
import { ApiError } from "@/lib/api";
import { analysisKeys, runAnalysis } from "@/lib/analysis";
import { currentUserKey } from "@/lib/auth";
import { useCloseOnHide } from "@/lib/use-close-on-hide";

/**
 * "Analyse with AI": hidden unless the server has an AI provider. The first
 * time, it asks for consent and says exactly what will be sent.
 */
export function AnalyseWithAI({ applicationId }: { applicationId: string }) {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: aiKeys.status, queryFn: getAIStatus });
  const [open, setOpen] = useState(false);
  const [understood, setUnderstood] = useState(false);
  useCloseOnHide(useCallback(() => setOpen(false), []));

  const consent = useMutation({
    mutationFn: setAIConsent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiKeys.status });
      queryClient.invalidateQueries({ queryKey: currentUserKey });
    },
  });
  const run = useMutation({
    mutationFn: () => runAnalysis(applicationId, "ai"),
    onSuccess: (result) => queryClient.setQueryData(analysisKeys.latest(applicationId), result),
  });

  const s = status.data;
  if (!s?.available) return null;

  async function turnOnAndRun() {
    await consent.mutateAsync(true);
    setOpen(false);
    run.mutate();
  }

  const error = run.error ?? consent.error;
  return (
    <div className="flex flex-col items-end gap-1">
      <Button size="sm" variant="outline" onClick={() => (s.consented ? run.mutate() : setOpen(true))} disabled={run.isPending}>
        <Sparkles aria-hidden />
        {run.isPending ? "Analysing with AI…" : "Analyse with AI"}
      </Button>
      {s.consented && (
        <button
          type="button"
          className="tap text-xs text-muted-foreground underline-offset-4 hover:underline"
          onClick={() => consent.mutate(false)}
          disabled={consent.isPending}
        >
          AI assistance is on · Turn off
        </button>
      )}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error instanceof ApiError ? error.message : "The AI analysis couldn't be started."}
        </p>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Analyse with AI?</DialogTitle>
            <DialogDescription>{s.data_sent}</DialogDescription>
          </DialogHeader>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
            <li>
              Every AI verdict is checked: it must point at a passage in your CV and quote it exactly. If it doesn&apos;t,
              the rule-based verdict is kept and you&apos;re told why.
            </li>
            <li>The AI describes what your CV shows. It never judges your ability.</li>
            <li>You can turn AI assistance off at any time; the rule-based analysis always works without it.</li>
          </ul>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-primary"
              checked={understood}
              onChange={(e) => setUnderstood(e.target.checked)}
            />
            I understand what will be sent to {s.provider}.
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={turnOnAndRun} disabled={!understood || consent.isPending}>
              Turn on and analyse
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
