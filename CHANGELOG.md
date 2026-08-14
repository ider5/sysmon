# Changelog

All notable changes to SysMon are documented in this file.

## [Unreleased]

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
- Process panel is a bordered table with rank, CPU bars, and colored memory; dashboard gives it a full-width row

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
