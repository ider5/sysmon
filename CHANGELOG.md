# Changelog

All notable changes to SysMon are documented in this file.

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
