from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timezone

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate heart-rate uploads to the LoveBeats backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--profile-id", default="demo_profile", help="Profile ID to update")
    parser.add_argument("--min-bpm", type=int, default=72, help="Minimum simulated BPM")
    parser.add_argument("--max-bpm", type=int, default=110, help="Maximum simulated BPM")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between uploads")
    parser.add_argument("--count", type=int, default=10, help="Number of updates to send")
    args = parser.parse_args()

    if args.min_bpm >= args.max_bpm:
        raise SystemExit("--min-bpm must be smaller than --max-bpm")

    base_url = args.base_url.rstrip("/")
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        for index in range(args.count):
            bpm = random.randint(args.min_bpm, args.max_bpm)
            payload = {
                "profile_id": args.profile_id,
                "bpm": bpm,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            response = client.post("/v1/heart-rate/latest", json=payload)
            response.raise_for_status()
            data = response.json()
            print(
                f"[{index + 1}/{args.count}] profile={data['profile_id']} bpm={data['bpm']} "
                f"status={data['status']} age_sec={data['age_sec']}"
            )
            if index < args.count - 1:
                time.sleep(args.interval)

    print("Heart-rate simulation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
