import { cn } from "cn";
import type { VariantProps } from "class-variance-authority";

import { buttonVariants } from "@/components/ui/button";

/**
 * Button styling for elements that aren't <Button>, such as a <Link>.
 * Runs the classes through cn() like <Button> does, so conflicting classes
 * from the base and the variant (e.g. two border colours) resolve correctly.
 */
export function buttonClass(options?: VariantProps<typeof buttonVariants>, className?: string) {
  return cn(buttonVariants(options), className);
}
