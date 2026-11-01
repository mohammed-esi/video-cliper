"""Development-only: render one 9:16 portrait clip from a local source video.

Usage (from backend/):
    .venv/bin/python -m scripts.render_portrait_clip VIDEO --start 144 --end 174
    .venv/bin/python -m scripts.render_portrait_clip VIDEO --start 0 --duration 30

Writes data/debug/<name>_portrait_<start>-<end>.mp4 (gitignored) using cached analysis
when available under data/debug/<name>/analysis/.
"""

import argparse
import sys
import time
from pathlib import Path

from app.core.config import Settings
from app.services.ffprobe import run_ffprobe
from app.services.portrait_render import render_portrait_clip

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEBUG_DIR = BACKEND_DIR / "data" / "debug"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--start", type=float, default=0.0)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--end", type=float)
    group.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    args = parser.parse_args()

    settings = Settings()
    source = args.video.expanduser().resolve()
    probe = run_ffprobe(source, settings)
    end = args.end if args.end is not None else min(args.start + args.duration, probe.duration_seconds)

    name = source.parent.name if source.name.startswith("source.") else source.stem
    analysis_dir = args.analysis_dir or DEBUG_DIR / name / "analysis"
    output = args.output or DEBUG_DIR / f"{name}_portrait_{args.start:.1f}-{end:.1f}.mp4"

    started = time.monotonic()
    result = render_portrait_clip(
        settings,
        source,
        analysis_dir,
        start_time=args.start,
        end_time=end,
        output_path=output,
    )
    total = time.monotonic() - started

    out_probe = run_ffprobe(result.output_path, settings)
    print(f"source={source}")
    print(f"range={result.start_time:.3f}-{result.end_time:.3f}s ({result.duration_seconds:.3f}s)")
    print(f"detection_cache_reused={result.detection_cache_reused}")
    print(f"analysis_seconds={result.analysis_seconds:.2f} render_seconds={result.render_seconds:.2f}")
    print(f"total_seconds={total:.2f}")
    print(
        f"output={result.output_path} "
        f"video={out_probe.width}x{out_probe.height} "
        f"duration={out_probe.duration_seconds:.3f}s audio={out_probe.has_audio}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
