"""Micro-benchmarks for pylsl's hot paths.

Measures the per-call cost of the Python/ctypes layer, independent of network
latency, by running an outlet and an inlet in the same process over loopback.
Pull benchmarks pre-fill the inlet buffer and then pull with timeout=0.0 so
the numbers reflect conversion overhead, not waiting time.

Usage:
    python -m bench.bench_pylsl               # default matrix
    python -m bench.bench_pylsl --channels 8 64 --json out.json
    python -m bench.bench_pylsl --only pull_chunk    # substring filter

Results are printed as a table and optionally written to JSON so that two
runs (e.g. before/after a change) can be compared with:
    python -m bench.bench_pylsl --compare before.json after.json
"""

from __future__ import annotations

import argparse
import ctypes
import json
import platform
import statistics
import sys
import time
import uuid

import numpy as np

import pylsl
from pylsl.lib import lib

# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class Result:
    def __init__(self, name, n_calls, seconds, n_samples=None, n_values=None):
        self.name = name
        self.n_calls = n_calls
        self.seconds = seconds
        self.n_samples = n_samples
        self.n_values = n_values

    @property
    def us_per_call(self):
        return 1e6 * self.seconds / self.n_calls

    @property
    def msamples_per_s(self):
        if not self.n_samples:
            return None
        return self.n_samples / self.seconds / 1e6

    @property
    def mvalues_per_s(self):
        if not self.n_values:
            return None
        return self.n_values / self.seconds / 1e6

    def to_dict(self):
        return {
            "name": self.name,
            "n_calls": self.n_calls,
            "seconds": self.seconds,
            "n_samples": self.n_samples,
            "n_values": self.n_values,
            "us_per_call": self.us_per_call,
            "msamples_per_s": self.msamples_per_s,
            "mvalues_per_s": self.mvalues_per_s,
        }


def timeit(fn, n_calls, repeats=5):
    """Run fn() n_calls times, `repeats` times; return the best wall time."""
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        for _ in range(n_calls):
            fn()
        best = min(best, time.perf_counter() - t0)
    return best


class Pair:
    """An outlet/inlet pair on the same machine with a warm connection."""

    def __init__(self, n_channels, fmt, srate=1000.0, max_buflen=60):
        self.n_channels = n_channels
        self.fmt = fmt
        name = f"bench_{fmt}_{n_channels}_{uuid.uuid4().hex[:8]}"
        self.info = pylsl.StreamInfo(name, "Bench", n_channels, srate, fmt, name)
        self.outlet = pylsl.StreamOutlet(
            self.info, chunk_size=0, max_buffered=max_buflen
        )
        found = pylsl.resolve_byprop("name", name, timeout=10.0)
        if not found:
            raise RuntimeError("could not resolve own bench stream")
        self.inlet = pylsl.StreamInlet(found[0], max_buflen=max_buflen, max_chunklen=0)
        self.inlet.open_stream(timeout=10.0)
        # warm-up: make sure the connection is established and buffers exist
        self.outlet.push_sample(self.make_sample())
        while self.inlet.pull_sample(timeout=1.0)[1] is None:
            self.outlet.push_sample(self.make_sample())
        self.inlet.flush()

    def make_sample(self):
        if self.fmt == "string":
            return [f"s{i}" for i in range(self.n_channels)]
        return [float(i) for i in range(self.n_channels)]

    def make_chunk_np(self, n_samples):
        dtype = {"float32": np.float32, "double64": np.float64, "int32": np.int32}[
            self.fmt
        ]
        return np.ascontiguousarray(
            np.arange(n_samples * self.n_channels, dtype=dtype).reshape(
                n_samples, self.n_channels
            )
        )

    def make_chunk_list(self, n_samples):
        return [self.make_sample() for _ in range(n_samples)]

    def fill(self, n_samples, chunk=1000):
        """Push n_samples into the outlet and wait until the inlet has them."""
        if self.fmt == "string":
            data = self.make_chunk_list(chunk)
            for _ in range(0, n_samples, chunk):
                self.outlet.push_chunk(data)
        else:
            data = self.make_chunk_np(chunk)
            for _ in range(0, n_samples, chunk):
                self.outlet.push_chunk(data)
        deadline = time.perf_counter() + 10.0
        while self.inlet.samples_available() < n_samples:
            if time.perf_counter() > deadline:
                raise RuntimeError(
                    f"inlet only has {self.inlet.samples_available()} of {n_samples}"
                )
            time.sleep(0.001)

    def close(self):
        self.inlet.close_stream()
        del self.inlet
        del self.outlet


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


def bench_ctypes_call_overhead():
    """Raw cost of a trivial ctypes call, with and without argtypes."""
    n = 200_000
    out = []
    # lsl_local_clock: no args, restype double already set.
    out.append(
        Result("ctypes.call lsl_local_clock()", n, timeit(lib.lsl_local_clock, n))
    )
    # lsl_protocol_version: no args, restype int (default)
    out.append(
        Result(
            "ctypes.call lsl_protocol_version()", n, timeit(lib.lsl_protocol_version, n)
        )
    )
    # A call with argument marshalling: lsl_samples_available(handle) is cheap
    # in C and takes one pointer, which lets us isolate marshalling cost.
    return out


def bench_samples_available(pair):
    n = 200_000
    inlet = pair.inlet
    f = lib.lsl_samples_available
    obj = inlet.obj
    without = Result(
        f"ctypes.call lsl_samples_available(handle) [argtypes unset] ch={pair.n_channels}",
        n,
        timeit(lambda: f(obj), n),
    )
    saved = f.argtypes
    try:
        f.argtypes = [ctypes.c_void_p]
        with_ = Result(
            f"ctypes.call lsl_samples_available(handle) [argtypes set] ch={pair.n_channels}",
            n,
            timeit(lambda: f(obj), n),
        )
    finally:
        f.argtypes = saved
    return [without, with_]


def bench_push_sample(pair):
    n = 20_000
    sample = pair.make_sample()
    outlet = pair.outlet
    r = Result(
        f"push_sample list {pair.fmt} ch={pair.n_channels}",
        n,
        timeit(lambda: outlet.push_sample(sample), n),
        n_samples=n,
        n_values=n * pair.n_channels,
    )
    pair.inlet.flush()
    return [r]


def bench_push_chunk(pair, n_samples=1000):
    n = 200
    outlet = pair.outlet
    out = []
    if pair.fmt != "string":
        arr = pair.make_chunk_np(n_samples)
        out.append(
            Result(
                f"push_chunk numpy {pair.fmt} ch={pair.n_channels} n={n_samples}",
                n,
                timeit(lambda: (outlet.push_chunk(arr), pair.inlet.flush()), n),
                n_samples=n * n_samples,
                n_values=n * n_samples * pair.n_channels,
            )
        )
    lst = pair.make_chunk_list(n_samples)
    out.append(
        Result(
            f"push_chunk list-of-lists {pair.fmt} ch={pair.n_channels} n={n_samples}",
            n,
            timeit(lambda: (outlet.push_chunk(lst), pair.inlet.flush()), n),
            n_samples=n * n_samples,
            n_values=n * n_samples * pair.n_channels,
        )
    )
    pair.inlet.flush()
    return out


def bench_pull_sample(pair):
    n = 20_000
    inlet = pair.inlet
    # Pre-fill so every pull is non-blocking.
    seconds = []
    for _ in range(3):
        pair.fill(n)
        t0 = time.perf_counter()
        for _ in range(n):
            s, ts = inlet.pull_sample(timeout=0.0)
            if ts is None:
                raise RuntimeError("buffer underrun during pull_sample bench")
        seconds.append(time.perf_counter() - t0)
        inlet.flush()
    return [
        Result(
            f"pull_sample {pair.fmt} ch={pair.n_channels}",
            n,
            min(seconds),
            n_samples=n,
            n_values=n * pair.n_channels,
        )
    ]


def bench_pull_chunk(pair, n_samples=1000):
    n = 50
    inlet = pair.inlet
    out = []

    def run(label, fn):
        seconds = []
        for _ in range(3):
            pair.fill(n * n_samples)
            t0 = time.perf_counter()
            for _ in range(n):
                fn()
            seconds.append(time.perf_counter() - t0)
            inlet.flush()
        out.append(
            Result(
                f"pull_chunk {label} {pair.fmt} ch={pair.n_channels} n={n_samples}",
                n,
                min(seconds),
                n_samples=n * n_samples,
                n_values=n * n_samples * pair.n_channels,
            )
        )

    def pull_list():
        samples, ts = inlet.pull_chunk(timeout=0.0, max_samples=n_samples)
        if len(ts) != n_samples:
            raise RuntimeError(f"short chunk: {len(ts)}")

    run("list", pull_list)

    if pair.fmt != "string":
        dest = pair.make_chunk_np(n_samples)

        def pull_dest():
            _, ts = inlet.pull_chunk(timeout=0.0, max_samples=n_samples, dest_obj=dest)
            if len(ts) != n_samples:
                raise RuntimeError(f"short chunk: {len(ts)}")

        run("dest_obj", pull_dest)
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def run_matrix(channels, formats, chunk, only=None):
    results = []

    def keep(r):
        return only is None or any(o in r.name for o in only)

    for r in bench_ctypes_call_overhead():
        if keep(r):
            results.append(r)
            print_row(r)

    for fmt in formats:
        for ch in channels:
            pair = Pair(ch, fmt)
            try:
                benches = [
                    bench_samples_available,
                    bench_push_sample,
                    lambda p: bench_push_chunk(p, chunk),
                    bench_pull_sample,
                    lambda p: bench_pull_chunk(p, chunk),
                ]
                for b in benches:
                    for r in b(pair):
                        if keep(r):
                            results.append(r)
                            print_row(r)
            finally:
                pair.close()
    return results


def print_header():
    print(f"{'benchmark':<72} {'us/call':>10} {'Msamp/s':>9} {'Mval/s':>9}")
    print("-" * 103)


def print_row(r):
    ms = f"{r.msamples_per_s:9.2f}" if r.msamples_per_s else f"{'':>9}"
    mv = f"{r.mvalues_per_s:9.2f}" if r.mvalues_per_s else f"{'':>9}"
    print(f"{r.name:<72} {r.us_per_call:10.2f} {ms} {mv}")


def env_info():
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": np.__version__,
        "pylsl": pylsl.__version__,
        "liblsl": pylsl.library_version(),
        "liblsl_info": pylsl.library_info(),
    }


def compare(before_path, after_path):
    before = {r["name"]: r for r in json.load(open(before_path))["results"]}
    after = {r["name"]: r for r in json.load(open(after_path))["results"]}
    print(f"{'benchmark':<72} {'before us':>10} {'after us':>10} {'speedup':>8}")
    print("-" * 103)
    ratios = []
    for name in before:
        if name not in after:
            continue
        b = before[name]["us_per_call"]
        a = after[name]["us_per_call"]
        ratios.append(b / a)
        print(f"{name:<72} {b:10.2f} {a:10.2f} {b / a:8.2f}x")
    if ratios:
        print(f"\ngeometric mean speedup: {statistics.geometric_mean(ratios):.2f}x")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--channels", type=int, nargs="+", default=[1, 8, 64])
    ap.add_argument(
        "--formats",
        nargs="+",
        default=["float32", "string"],
        choices=["float32", "double64", "int32", "string"],
    )
    ap.add_argument("--chunk", type=int, default=1000, help="samples per chunk")
    ap.add_argument("--only", nargs="+", help="substring filter on benchmark names")
    ap.add_argument("--json", help="write results to this JSON file")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = ap.parse_args(argv)

    if args.compare:
        compare(*args.compare)
        return

    info = env_info()
    for k, v in info.items():
        print(f"{k}: {v}")
    print()
    print_header()
    results = run_matrix(args.channels, args.formats, args.chunk, args.only)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(
                {"env": info, "results": [r.to_dict() for r in results]}, f, indent=1
            )
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
