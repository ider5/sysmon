# Changelog

All notable changes to SysMon are documented in this file.

## [Unreleased]

### Added
- Dashboard shows battery charge, power state, and temperatures when `[modules] sensors = true`
- `sysmon snapshot sensors` prints that same panel; the full snapshot includes it when the module is enabled
- `sysmon sensors` prints battery and temperatures, with the same JSON section as the other metric commands
- `sysmon config show` prints the resolved configuration as JSON
- Prometheus `/metrics` exports battery charge and sensor temperatures when they are present in the payload
- Prometheus `/metrics` exports per-mount disk utilization and per-interface network speeds when those lists are present
- Prometheus `/metrics` exports GPU memory and temperature alongside utilization
- Prometheus `/metrics` exports swap utilization and size when swap is present
- Prometheus `/metrics` exports aggregate disk read and write throughput
- Prometheus `/metrics` exports network and disk byte totals as counters
- Prometheus `/metrics` exports memory used, available, and total bytes

### Changed
- The dashboard keeps sparklines for memory, disk read/write speed, and upload speed, next to the existing CPU and download history
- Sparklines fill missing history with the first real sample, so a short trail does not look like a jump up from zero
- Sparkline history drops NaN and infinite samples instead of crashing the dashboard
- Progress bars render `n/a` for NaN or infinite percentages instead of crashing the dashboard
- JSON metric status is `unknown` for a NaN or infinite percentage instead of `ok`
- `sysmon serve` returns HTTP 500 JSON when a scrape fails, and later requests still succeed
- The dashboard stays open when one frame fails to render and shows that error until the next successful frame
- The dashboard and `sysmon serve` reload `config.toml` when the file changes, without a restart
- `sysmon snapshot` and `sysmon serve` only sample network and disk counters when those modules are enabled. Snapshot also skips that wait for sections that do not need it
- Brief mode and the terminal title follow `[modules]` (and `enable_gpu`); a battery reading and the hottest temperature are included when sensors are enabled. Swap usage is appended only while swap is actually in use
- `sysmon brief --format json` uses those same module switches and includes `sensors` when the module is enabled

### Fixed
- Aggregate network collection returns zero counters instead of crashing when the OS exposes no I/O counters
- CPU physical core count falls back to the logical count when the OS does not report it, instead of rendering "None cores"
- The native process scanner drops idle placeholders and the current process before applying the top-N limit, so the list is not shortened by those rows
- Linux DRM GPUs are ordered by card number, so `card10` no longer sorts before `card2`
- Config intervals are clamped to 0.1–10 seconds, `process_limit` to 1–50, and a warn threshold above critical is swapped so the warning band still exists. A single string for `disk_mounts` or `network_interfaces` is kept as one entry instead of being split into characters. A non-table `modules` or `thresholds` value is ignored instead of discarding the rest of the file
- CI runs on `master` only
- Interactive `sysmon top --watch` treats `c`, `m`, `q`, and `/` as text while a name filter is being typed
- A GPU temperature of 0°C is shown instead of being treated as missing
- An unreadable selected disk mount stays in the result at zero usage instead of being replaced by the primary disk
- A selected network interface that is not present stays in the per-interface list at zero instead of disappearing

## [0.4.0] - 2026-08-14

### Added
- Optional Rust process backend (`sysmon._core`) compiled when `rustc` is available; psutil fallback otherwise
- Platform config directories (Windows `%APPDATA%`, macOS Application Support) with legacy `~/.config/sysmon` fallback
- Dedicated GPU warn/critical thresholds
- Linux DRM sysfs GPU backend for AMD (and other cards exposing `gpu_busy_percent`) when NVIDIA libraries are unavailable; NVIDIA and sysfs results are merged
- `sysmon serve` localhost HTTP JSON (`/json`) and Prometheus (`/metrics`) endpoints
- Opt-in `sensors` collector (battery/temperatures), default off

### Changed
- Version bumped to 0.4.0; JSON `schema_version` remains 3
- `[dev]` extra is tooling-only (`pyinstaller`, `pytest`, `ruff`, `shtab`); GPU libraries stay in `[gpu]`
- CLI snapshot/top/cpu/memory/network/disk/gpu collect through `registry.collect` (same path as dashboard/export)
- CollectorService samples enabled modules in parallel and returns a shallow snapshot copy
- Process scan uses batched `process_iter` attrs and `heapq.nlargest` instead of a full sort
- Brief/dashboard GPU colors follow `metric_status` (no hardcoded 60% yellow band)
- CI matrix includes macOS (Python 3.11 only, matching Windows) and a rich-default snapshot smoke test
- CPU frequency collector thread starts only on Windows
- Process panel is a bordered table with rank, CPU bars, and colored memory; dashboard gives it a full-width row

### Removed
- Unused `color_percent` and `metric_row` display helpers

### Fixed
- CPU frequency falls back to 0 when `psutil.cpu_freq` is missing (macOS CI / some ARM hosts)
- Windows consoles that default to cp1252 no longer crash on snapshot emoji
- Brief mode colors now honor configured warn/critical thresholds instead of a hardcoded 60/80 split
- Renamed `build.py` to `scripts/build_exe.py` so `python -m build` is not shadowed during PyPI publish
- Title mode now writes OSC title sequences to the user terminal and verifies the worker started
- Bare `sysmon` launches the dashboard (matching README)
- CollectorService isolates per-module collection errors and can restart after a failed `start()`
- Process CPU percentages use a pid-level sample cache so `sysmon top` is no longer stuck at 0%
- Native process backend skips Linux userland threads and waits at least 250ms between CPU samples
- `sysmon serve` binds IPv6 loopback (`::1`) and primes network/disk counters before the first scrape
- Brief mode honors `network_interfaces` and `sample_interval`
- Dashboard no longer falls back to blocking collectors on the UI thread
- Invalid `--sort` values and unreadable config files now surface errors instead of failing silently
- GPU NVML is initialized once per process instead of on every sample
- Network aggregate totals follow the selected interfaces; disk/network speeds clamp counter resets to 0
- Process lists hide OS idle placeholders (`System Idle Process`, `Idle`, `System Interrupts`, pid 0, Linux `swapper`)
- Process lists hide the running sysmon process itself (often `python.exe` when launched from source)
- Default CI test jobs skip the optional Rust extension via `SYSMON_SKIP_NATIVE` so Windows images with preinstalled Cargo do not compile `sysmon._core`

## [0.3.0] - 2026-06-30

### Added
- Multi-disk monitoring: enumerate mount points; `disk_mounts` config for selection
- Multi-network monitoring: per-interface stats; `network_interfaces` config for selection
- Interactive `sysmon top --watch` with runtime sort (c/m) and name filter (/)
- Background `CollectorService` for cached snapshots; dashboard reads cache
- Optional `gpu` extra (`pip install sysmon[gpu]`) for NVIDIA dependencies
- PyPI publish workflow (`.github/workflows/publish.yml`)

### Changed
- Version bumped to 0.3.0; JSON schema_version to 3 (disk `mounts`, network `interfaces`)
- Replaced deprecated `typer[all]` with `typer>=0.9.0`
- GPU libraries (GPUtil, nvidia-ml-py) moved from core to optional `[gpu]` extra
- Disk/network export payloads include multi-mount and per-interface data

### Fixed
- Dashboard collection no longer blocks UI thread during metric sampling

## [0.2.0] - 2026-06-29

### Added
- JSON export (`--format json`) for snapshot, brief, and individual metric commands
- Disk usage and I/O monitoring (`sysmon disk`, dashboard panel)
- TOML configuration (`sysmon config init`) with module toggles and thresholds
- Process Top N monitoring (`sysmon top`, dashboard panel)
- Dashboard sparkline history for CPU and network download speed
- Shell completion via `--print-completion` (requires `shtab`)
- Collector plugin registry for extensible metric collection
- NVIDIA GPU support via pynvml with GPUtil fallback
- GitHub Actions Release workflow for multi-platform binaries
- Windows CI matrix and CLI smoke tests

### Changed
- CPU frequency collector: lazy startup, merged sampling, PowerShell CIM instead of wmic
- Title mode: dedicated `title_worker` module with safer PID handling
- Dashboard layout: dynamic grid based on enabled modules
- Shared UI panels extracted to `display/panels.py`
- PyInstaller build: relative paths and hidden imports

### Fixed
- Hardcoded title error log path (now `~/.sysmon/title_error.log`)
- Network/disk speed sampling race with thread locks
- Cross-platform executable naming in `build.py`

## [0.1.0] - Initial release

### Added
- Real-time dashboard, snapshot, brief, and title modes
- CPU, memory, network, and NVIDIA GPU monitoring
- Rich terminal UI with gradient progress bars
- Windows real-time CPU frequency via Performance Counters
