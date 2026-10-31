import { Film, ScanFace, SlidersHorizontal } from "lucide-react";

import { BackendStatus } from "@/components/BackendStatus";
import { AppHeader } from "@/components/layout/AppHeader";
import { ImportScreen } from "@/features/import/ImportScreen";

const HIGHLIGHTS = [
  {
    icon: Film,
    title: "Automatic clips",
    description: "Your video is split into short, ready-to-review clips.",
  },
  {
    icon: SlidersHorizontal,
    title: "Precise trimming",
    description: "Adjust where each clip starts and ends, down to a tenth of a second.",
  },
  {
    icon: ScanFace,
    title: "Vertical, subject-aware",
    description: "Exports in 9:16, with the crop following the speaker.",
  },
] as const;

export default function Home() {
  return (
    <>
      <AppHeader currentStep="import" status={<BackendStatus />} />
      <main id="main" className="flex-1">
        <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-10 sm:px-6 md:py-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,32rem)] lg:gap-x-16 lg:gap-y-8 lg:py-24">
          <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 lg:mx-0 lg:max-w-xl lg:pt-6">
            <p className="text-dense font-medium tracking-wide text-accent uppercase">
              Long video in, vertical clips out
            </p>
            <h1 className="text-display font-semibold sm:text-4xl/tight">
              Turn long videos into short, vertical clips.
            </h1>
            <p className="text-base text-fg-muted sm:text-lg">
              Import a YouTube video or a file from your computer. You&apos;ll
              review the suggested clips, fine-tune them, and export them for
              Shorts, Reels and TikTok.
            </p>
          </div>

          <div className="mx-auto w-full max-w-2xl lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:max-w-none">
            <ImportScreen />
          </div>

          <ul className="mx-auto flex w-full max-w-2xl flex-col gap-4 md:flex-row md:gap-6 lg:mx-0 lg:max-w-xl lg:flex-col lg:gap-4">
            {HIGHLIGHTS.map(({ icon: Icon, title, description }) => (
              <li key={title} className="flex flex-1 gap-3">
                <span
                  className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-surface text-fg-muted"
                  aria-hidden
                >
                  <Icon className="size-4" />
                </span>
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-fg">{title}</span>
                  <span className="text-sm text-fg-muted">{description}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </main>
    </>
  );
}
