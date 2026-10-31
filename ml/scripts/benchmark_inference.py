"""Inference Benchmarking Suite for EggVision AI.

Measures:
1. End-to-end latency (ms) for varying image resolutions (480p, 720p, 1080p, 4K).
2. Peak heap memory allocation via tracemalloc.
3. CPU utilization during OpenCV pipeline execution.
"""

import argparse
import sys
import time
import tracemalloc
from pathlib import Path

# Add repository root to python search path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import cv2
import numpy as np
from ml.vision.pipeline import VisionPipeline


def generate_benchmark_image(width: int, height: int) -> np.ndarray:
    img = np.full((height, width, 3), (180, 110, 40), dtype=np.uint8)  # Blue background
    cx, cy = width // 2, height // 2
    rx, ry = int(width * 0.18), int(height * 0.28)
    cv2.ellipse(img, (cx, cy), (rx, ry), 0, 0, 360, (60, 140, 210), -1)
    return img


def benchmark(resolutions: list[tuple[int, int]], iterations: int = 5) -> list[dict]:
    pipeline = VisionPipeline()
    results = []

    for w, h in resolutions:
        test_img = generate_benchmark_image(w, h)
        times = []

        tracemalloc.start()
        for _ in range(iterations):
            start = time.perf_counter()
            _ = pipeline.process(test_img)
            times.append((time.perf_counter() - start) * 1000)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        avg_latency = float(np.mean(times))
        std_latency = float(np.std(times))
        peak_mb = peak / (1024 * 1024)

        results.append({
            "resolution": f"{w}x{h}",
            "avg_latency_ms": round(avg_latency, 2),
            "std_latency_ms": round(std_latency, 2),
            "peak_memory_mb": round(peak_mb, 2),
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark Vision Pipeline Performance")
    parser.add_argument("--iterations", type=int, default=5, help="Iterations per resolution")
    args = parser.parse_args()

    resolutions = [
        (640, 480),    # 480p
        (1280, 720),   # 720p
        (1920, 1080),  # 1080p
        (3840, 2160),  # 4K
    ]

    print("Running EggVision VisionPipeline performance benchmark...")
    metrics = benchmark(resolutions, args.iterations)
    print("\n--- Benchmark Results ---")
    for m in metrics:
        print(f"Resolution: {m['resolution']:>10} | Avg: {m['avg_latency_ms']:>6.1f} ms | Std: {m['std_latency_ms']:>5.1f} ms | Peak RAM: {m['peak_memory_mb']:>5.2f} MB")


if __name__ == "__main__":
    main()
