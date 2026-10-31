import { BackendStatus } from "@/components/BackendStatus";

export default function Home() {
  return (
    <div className="flex min-h-full flex-1 flex-col items-center justify-center px-6 py-16 sm:px-8">
      <main className="mx-auto w-full max-w-2xl text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl">
          Video Clipper
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-zinc-600 sm:mt-6 sm:text-xl">
          Turn long videos into short, vertical clips.
        </p>
        <BackendStatus />
      </main>
    </div>
  );
}
