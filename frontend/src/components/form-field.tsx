import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";

type FieldProps = {
  id: string;
  label: string;
  optional?: boolean;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
};

/** Label + control + hint/error, wired together for screen readers. */
export function FormField({ id, label, optional, hint, error, children, className }: FieldProps) {
  return (
    <div className={`flex flex-col gap-1.5 ${className ?? ""}`}>
      <Label htmlFor={id}>
        {label}
        {optional && <span className="font-normal text-muted-foreground">(optional)</span>}
      </Label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-xs text-muted-foreground">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

/** Props that connect an input to its FormField's hint or error text. */
export function describedBy(id: string, error?: string, hasHint = false) {
  return {
    "aria-invalid": error ? true : undefined,
    "aria-describedby": error ? `${id}-error` : hasHint ? `${id}-hint` : undefined,
  } as const;
}

export type FieldErrors = Record<string, string>;

/** Turns the API's 422 details into {fieldName: message}; anything else into a form-level message. */
export function readApiError(error: unknown): { fields: FieldErrors; form: string | null } {
  if (error instanceof ApiError && error.code === "validation_error" && Array.isArray(error.details)) {
    const fields: FieldErrors = {};
    for (const detail of error.details as { loc: (string | number)[]; msg: string }[]) {
      const name = detail.loc.find((part) => typeof part === "string" && part !== "body");
      if (typeof name === "string" && !fields[name]) fields[name] = detail.msg.replace(/^Value error, /, "");
    }
    return Object.keys(fields).length
      ? { fields, form: null }
      : { fields, form: "Some values are invalid. Check the form and try again." };
  }
  if (error instanceof ApiError) return { fields: {}, form: error.message };
  return { fields: {}, form: "Something went wrong. Please try again." };
}
