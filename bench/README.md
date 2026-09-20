# pylsl benchmarks

Micro-benchmarks for the Python/ctypes layer. An outlet and inlet run in the
same process; pull benchmarks pre-fill the inlet buffer and pull with
`timeout=0.0`, so results measure conversion overhead rather than network or
waiting time.

```sh
uv run python -m bench.bench_pylsl                       # default matrix
uv run python -m bench.bench_pylsl --json before.json    # save a baseline
# ... make changes ...
uv run python -m bench.bench_pylsl --json after.json
uv run python -m bench.bench_pylsl --compare before.json after.json
```

Options: `--channels 1 8 64`, `--formats float32 double64 int32 string`,
`--chunk 1000`, `--only pull_chunk` (substring filter).

Numbers vary between machines; compare runs only on the same machine with the
same liblsl. The `bench/` directory is not part of the distributed package.
