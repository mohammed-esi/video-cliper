"use client";

import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { ListVideo } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";

import { ClipCard, type ClipCardStatus } from "./ClipCard";

export interface ClipListItem {
  id: string;
  title: string;
  start: number;
  end: number;
  thumbnailUrl?: string;
  status?: ClipCardStatus;
  errorMessage?: string;
}

export interface ClipListProps {
  clips: ReadonlyArray<ClipListItem>;
  activeClipId: string | null;
  selectedIds: ReadonlySet<string>;
  onActivate: (id: string) => void;
  onSelectionChange: (selectedIds: Set<string>) => void;
  /** Per-clip export control, usually `<ClipExportControl size="sm" … />`. */
  renderExport?: (clip: ClipListItem) => ReactNode;
  /** Shows placeholder cards while clips are being generated. */
  isLoading?: boolean;
  /** Replaces the list with an error and optional retry. */
  error?: string | null;
  onRetry?: () => void;
  /** Action for the empty state, e.g. a link back to import. */
  emptyAction?: ReactNode;
  title?: string;
}

const SKELETON_COUNT = 4;

/** Clip rail: select-all, the clip cards, and arrow-key navigation between them. */
export function ClipList({
  clips,
  activeClipId,
  selectedIds,
  onActivate,
  onSelectionChange,
  renderExport,
  isLoading = false,
  error,
  onRetry,
  emptyAction,
  title = "Clips",
}: ClipListProps) {
  const listRef = useRef<HTMLUListElement>(null);
  const headingId = useId();
  const hintId = useId();

  const selectedCount = clips.filter((clip) => selectedIds.has(clip.id)).length;
  const allSelected = clips.length > 0 && selectedCount === clips.length;
  const someSelected = selectedCount > 0 && !allSelected;

  function toggleClip(id: string, selected: boolean) {
    const next = new Set(selectedIds);
    if (selected) {
      next.add(id);
    } else {
      next.delete(id);
    }
    onSelectionChange(next);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLUListElement>) {
    const buttons = Array.from(
      listRef.current?.querySelectorAll<HTMLButtonElement>(
        "[data-clip-activate]",
      ) ?? [],
    );
    const currentItem = (event.target as HTMLElement).closest("li");
    const index = Array.from(listRef.current?.children ?? []).indexOf(
      currentItem as Element,
    );
    const nextIndex = {
      ArrowDown: Math.min(index + 1, buttons.length - 1),
      ArrowUp: Math.max(index - 1, 0),
      Home: 0,
      End: buttons.length - 1,
    }[event.key];

    if (nextIndex === undefined || index === -1) {
      return;
    }
    event.preventDefault();
    buttons[nextIndex]?.focus();
  }

  const showClips = !isLoading && !error && clips.length > 0;

  return (
    <section aria-labelledby={headingId} className="flex flex-col">
      <header className="sticky top-0 z-(--z-sticky) flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-3">
        <h2
          id={headingId}
          className="flex items-center gap-2 text-sm font-semibold"
        >
          {title}
          {clips.length > 0 && (
            <span className="rounded-full bg-surface-raised px-2 py-0.5 font-mono text-xs font-medium text-fg-muted tabular-nums">
              {clips.length}
            </span>
          )}
        </h2>
        {showClips && (
          <label className="flex cursor-pointer items-center gap-2 text-dense text-fg-muted hover:text-fg">
            <input
              type="checkbox"
              checked={allSelected}
              ref={(element) => {
                if (element) {
                  element.indeterminate = someSelected;
                }
              }}
              onChange={() =>
                onSelectionChange(
                  allSelected
                    ? new Set()
                    : new Set(clips.map((clip) => clip.id)),
                )
              }
              className="size-4 cursor-pointer accent-accent"
            />
            Select all
          </label>
        )}
      </header>

      {isLoading && (
        <ul
          aria-label="Loading clips"
          aria-busy
          className="flex flex-col gap-2 p-3"
        >
          {Array.from({ length: SKELETON_COUNT }, (_, index) => (
            <li
              key={index}
              className="flex animate-pulse gap-3 rounded-md border border-border p-2.5"
            >
              <span className="aspect-video w-24 rounded-sm bg-surface-raised" />
              <span className="flex flex-1 flex-col gap-2 pt-1">
                <span className="h-3 w-3/4 rounded-sm bg-surface-raised" />
                <span className="h-2.5 w-1/2 rounded-sm bg-surface-raised" />
              </span>
            </li>
          ))}
        </ul>
      )}

      {!isLoading && error && (
        <ErrorState
          size="sm"
          title="Clips couldn't load"
          message={error}
          onRetry={onRetry}
        />
      )}

      {!isLoading && !error && clips.length === 0 && (
        <EmptyState
          size="sm"
          icon={<ListVideo />}
          title="No clips yet"
          description="Clips appear here once your video has been analyzed."
          action={emptyAction}
        />
      )}

      {showClips && (
        <>
          <p id={hintId} className="sr-only">
            Use the up and down arrow keys to move between clips.
          </p>
          <ul
            ref={listRef}
            aria-describedby={hintId}
            onKeyDown={handleKeyDown}
            className="flex flex-col gap-2 p-3"
          >
            {clips.map((clip) => (
              <li key={clip.id}>
                <ClipCard
                  title={clip.title}
                  start={clip.start}
                  end={clip.end}
                  thumbnailUrl={clip.thumbnailUrl}
                  status={clip.status}
                  errorMessage={clip.errorMessage}
                  isActive={clip.id === activeClipId}
                  isSelected={selectedIds.has(clip.id)}
                  onActivate={() => onActivate(clip.id)}
                  onSelectedChange={(selected) => toggleClip(clip.id, selected)}
                  exportSlot={renderExport?.(clip)}
                />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
