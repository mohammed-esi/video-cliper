export function buildClipExportFileName(
  clipTitle: string,
  startTime: number,
  endTime: number,
): string {
  const safeTitle = clipTitle
    .trim()
    .replace(/[^\w\-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40);
  const stem = safeTitle || "clip";
  return `${stem}_${startTime.toFixed(1)}-${endTime.toFixed(1)}.mp4`;
}

export function exportTrimChanged(
  expectedRevision: string,
  currentRevision: string | null,
): boolean {
  return currentRevision !== expectedRevision;
}

export function triggerPortraitDownload(url: string): void {
  const frame = document.createElement("iframe");
  frame.style.display = "none";
  frame.src = url;
  document.body.appendChild(frame);
  window.setTimeout(() => {
    frame.remove();
  }, 60_000);
}
