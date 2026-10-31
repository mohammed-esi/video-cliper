"use client";

import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

export interface TabItem<T extends string> {
  id: T;
  label: string;
  icon?: LucideIcon;
}

export interface TabsProps<T extends string> {
  /** Accessible name for the tab list. */
  label: string;
  items: ReadonlyArray<TabItem<T>>;
  value: T;
  onValueChange: (value: T) => void;
  /** Locks the current tab, e.g. while a submission is in flight. */
  disabled?: boolean;
  /** Content of the selected tab. */
  children: ReactNode;
}

/** WAI-ARIA tabs with automatic activation and arrow/Home/End keys. */
export function Tabs<T extends string>({
  label,
  items,
  value,
  onValueChange,
  disabled = false,
  children,
}: TabsProps<T>) {
  const baseId = useId();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = items.findIndex((item) => item.id === value);
  const panelId = `${baseId}-panel`;
  const tabId = (id: T) => `${baseId}-tab-${id}`;

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const last = items.length - 1;
    const nextIndex = {
      ArrowRight: selectedIndex === last ? 0 : selectedIndex + 1,
      ArrowLeft: selectedIndex === 0 ? last : selectedIndex - 1,
      Home: 0,
      End: last,
    }[event.key];

    if (nextIndex === undefined || disabled) {
      return;
    }

    event.preventDefault();
    onValueChange(items[nextIndex].id);
    tabRefs.current[nextIndex]?.focus();
  }

  return (
    <div className="flex flex-col gap-5">
      <div
        role="tablist"
        aria-label={label}
        onKeyDown={handleKeyDown}
        className="grid auto-cols-fr grid-flow-col gap-1 rounded-md border border-border bg-bg p-1"
      >
        {items.map((item, index) => {
          const isSelected = item.id === value;
          const Icon = item.icon;

          return (
            <button
              key={item.id}
              ref={(element) => {
                tabRefs.current[index] = element;
              }}
              type="button"
              role="tab"
              id={tabId(item.id)}
              aria-selected={isSelected}
              aria-controls={isSelected ? panelId : undefined}
              tabIndex={isSelected ? 0 : -1}
              disabled={disabled && !isSelected}
              onClick={() => onValueChange(item.id)}
              className={cn(
                "inline-flex h-9 items-center justify-center gap-2 rounded-sm px-3 text-sm font-medium",
                "transition-colors duration-(--dur-fast) ease-out",
                "disabled:cursor-not-allowed disabled:opacity-50",
                isSelected
                  ? "bg-surface-raised text-fg shadow-sm"
                  : "text-fg-muted hover:text-fg",
              )}
            >
              {Icon && <Icon className="size-4" aria-hidden />}
              {item.label}
            </button>
          );
        })}
      </div>
      <div role="tabpanel" id={panelId} aria-labelledby={tabId(value)}>
        {children}
      </div>
    </div>
  );
}
