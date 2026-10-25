"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState, type FormEvent } from "react";

import { FormField, readApiError } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { applicationKeys, updateApplication, type ApplicationDetail, type ApplicationStatus } from "@/lib/applications";
import { APPLICATION_STATUS, APPLICATION_STATUS_ORDER } from "@/lib/labels";
import { useCloseOnHide } from "@/lib/use-close-on-hide";

export function StatusDialog({ application }: { application: ApplicationDetail }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useCloseOnHide(useCallback(() => setOpen(false), []));

  const mutation = useMutation({
    mutationFn: (body: { status: ApplicationStatus; change_reason: string | null }) =>
      updateApplication(application.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      setOpen(false);
    },
    onError: (err) => setError(readApiError(err).form ?? "Check the values and try again."),
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const status = String(data.get("status")) as ApplicationStatus;
    const reason = String(data.get("change_reason") ?? "").trim();
    if (status === application.status) {
      setOpen(false);
      return;
    }
    setError(null);
    mutation.mutate({ status, change_reason: reason || null });
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        Change status
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={onSubmit} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Change application status</DialogTitle>
              <DialogDescription>
                The change is added to this application&apos;s history. Round results don&apos;t change it
                automatically, so update it here when you hear back.
              </DialogDescription>
            </DialogHeader>
            <FormField id="new-status" label="New status">
              <NativeSelect id="new-status" name="status" defaultValue={application.status}>
                {APPLICATION_STATUS_ORDER.map((value) => (
                  <option key={value} value={value}>
                    {APPLICATION_STATUS[value].label}
                  </option>
                ))}
              </NativeSelect>
            </FormField>
            <FormField id="status-reason" label="Reason or note" optional hint='For example "Recruiter email on 3 Nov".'>
              <Textarea id="status-reason" name="change_reason" rows={2} maxLength={1000} aria-describedby="status-reason-hint" />
            </FormField>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Saving…" : "Save status"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
