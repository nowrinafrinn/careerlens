"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

const EASE = "cubic-bezier(0.16, 0.84, 0.24, 1)";

/**
 * On every navigation, the page rises out of depth and its sections follow in
 * quick succession. Animating (rather than remounting with a key) keeps each
 * page's state, including pages Next keeps mounted while hidden.
 */
export function PageTransition({ stageId }: { stageId: string }) {
  const pathname = usePathname();

  useEffect(() => {
    const stage = document.getElementById(stageId);
    if (!stage || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    stage.animate(
      [
        { opacity: 0, transform: "perspective(1200px) translate3d(0, 24px, -300px) rotateX(10deg)" },
        { opacity: 1, transform: "perspective(1200px) translate3d(0, 0, 0) rotateX(0)" },
      ],
      { duration: 700, easing: EASE },
    );

    // Hidden (kept-mounted) pages have no layout boxes; stagger the visible one's sections.
    const page = Array.from(stage.children).find((el) => el.getClientRects().length > 0);
    Array.from(page?.children ?? [])
      .slice(0, 8)
      .forEach((section, index) => {
        section.animate(
          [
            { opacity: 0, transform: "translateY(10px) scale(0.985)" },
            { opacity: 1, transform: "none" },
          ],
          { duration: 500, delay: 80 + Math.min(index, 4) * 50, easing: EASE, fill: "backwards" },
        );
      });
  }, [pathname, stageId]);

  return null;
}
