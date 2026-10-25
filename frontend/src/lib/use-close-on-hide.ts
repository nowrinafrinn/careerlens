import { useLayoutEffect } from "react";

/**
 * Next.js keeps recently visited pages mounted but hidden (React <Activity>),
 * so a dialog left open would still be open when you come back. The cleanup
 * runs when the page is hidden and closes it.
 */
export function useCloseOnHide(close: () => void) {
  useLayoutEffect(() => close, [close]);
}
