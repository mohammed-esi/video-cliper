import type { ReactNode } from "react";

export interface EditorLayoutProps {
  /** Clip rail, usually ClipList. */
  clips: ReactNode;
  /** Main column: VideoStage, PlayerControls and Trimmer. */
  stage: ReactNode;
  /** Details for the active clip: VerticalPreview, TimeRangeFields, ClipExportControl. */
  inspector: ReactNode;
  /** Pinned to the bottom, usually ExportBar. */
  footer?: ReactNode;
  stageLabel?: string;
  inspectorLabel?: string;
}

/**
 * The editor workspace below AppHeader. It renders <main id="main"> (the skip
 * link target) and, from tablet up, fills the viewport with independently
 * scrolling panels.
 *
 * - xl and up: clip rail | stage | inspector (inspector stays in view)
 * - md to xl:  clip rail | stage with the inspector below it
 * - below md:  stage, inspector, then clips, in one column
 */
export function EditorLayout({
  clips,
  stage,
  inspector,
  footer,
  stageLabel = "Video editor",
  inspectorLabel = "Clip details",
}: EditorLayoutProps) {
  return (
    <main
      id="main"
      className="flex flex-col md:h-[calc(100dvh-var(--header-height))]"
    >
      {/* Scroll panes are positioned so absolutely placed children (e.g. sr-only
          text) stay inside them instead of extending the page. */}
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <div className="relative order-last border-t border-border bg-surface md:order-none md:w-70 md:shrink-0 md:overflow-y-auto md:border-t-0 md:border-r xl:w-80">
          {clips}
        </div>

        <div className="relative min-w-0 flex-1 md:overflow-y-auto">
          <div className="grid gap-4 p-4 lg:gap-6 lg:p-6 xl:grid-cols-[minmax(0,1fr)_21rem] xl:items-start">
            <section
              aria-label={stageLabel}
              className="flex min-w-0 flex-col gap-4 rounded-lg border border-border bg-surface p-4"
            >
              {stage}
            </section>
            <aside
              aria-label={inspectorLabel}
              className="flex min-w-0 flex-col gap-6 rounded-lg border border-border bg-surface p-4 xl:sticky xl:top-6"
            >
              {inspector}
            </aside>
          </div>
        </div>
      </div>

      {footer && (
        <div className="sticky bottom-0 z-(--z-sticky) shrink-0">{footer}</div>
      )}
    </main>
  );
}
