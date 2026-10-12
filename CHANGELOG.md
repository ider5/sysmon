# Changelog

All notable changes to SysMon are documented in this file.

## [Unreleased]

### Added
- Dashboard shows battery charge, power state, and temperatures when `[modules] sensors = true`
- Sensor collection keeps the rest of the sample when a battery or temperature value is not a number
- The sensors panel keeps drawing when a battery or temperature field is missing or not a number
- The sensors panel lists the hottest temperatures first, so the eight visible rows are the highest readings
- A non-finite temperature is left out of the GPU panel, brief line, terminal title, and hottest-sensor selection
- CPU snapshots, the CPU panel, JSON, and Prometheus include the 1, 5, and 15 minute load average when the OS provides it
- Prometheus exports logical and physical CPU counts so load average can be compared with the machine size
- Prometheus output skips a metric whose value is missing or non-finite instead of failing the whole scrape
- Prometheus load average, per-mount disk percent, per-interface throughput, and temperature series also skip non-finite and boolean samples instead of writing `inf` or `nan`
- Brief mode and the terminal title append the 1-minute load when it is at least the logical CPU count
- `sysmon cpu` and the CPU snapshot show per-core usage, not only the dashboard's compact panel
- `sysmon cpu` still prints the CPU panel when the per-core list is missing or not a list
- The CPU panel ignores a per-core list that is not a list instead of failing the frame
- The snapshot header includes the sysmon version
- `sysmon memory` and the memory snapshot show available RAM, matching the dashboard
- Disk panels show free space next to used and total when the collector provides it, and a partial mount or speed record does not crash the panel
- The disk panel skips a mount entry that is not a record, and ignores a non-finite size instead of printing `inf` or `nan`
- Disk collection reports inode usage on platforms with `statvfs`, and the panel, JSON, and Prometheus include it per mount as well as for the primary disk
- Listing disk mounts returns an empty list when the OS partition call fails, instead of failing the caller
- Inode usage is omitted when the OS counters are not finite numbers, instead of failing the disk sample
- Disk mounts include the filesystem type, shown next to the mount point and as `sysmon_disk_mount_info`, when the OS reports it
- JSON disk mounts tolerate a record that omits used, free, or total instead of dropping the disk section
- JSON disk section stays present when the primary record omits sizes or speeds, and a mount entry that is not a record is skipped
- JSON network totals tolerate a record that omits speeds, packets, or error counts instead of dropping the network section
- JSON network interfaces drop entries that are not records
- JSON CPU and memory sections tolerate a partial record instead of dropping the section
- JSON GPU entries tolerate a partial record. A temperature of 0°C is kept, and a missing temperature stays null
- Network panels tolerate a partial interface or totals record instead of raising
- The network panel does not draw a divider before the first real interface when an earlier entry is not a record
- Network collection reports inbound and outbound errors and drops. The panel, brief line, and terminal title show them when any are non-zero, and Prometheus exports them as counters
- A non-finite NIC error counter is reported as zero instead of failing the network sample
- A non-numeric network byte or packet counter is treated as zero instead of failing the network sample
- Network interfaces include link speed in Mb/s when the OS reports it, on the panel and as `sysmon_network_interface_speed_mbps`
- Network interfaces include whether the link is up, and the panel says `down` when it is not. Prometheus exports `sysmon_network_interface_up`. The brief line and terminal title append `DOWN` plus the interface name
- The network panel ignores a non-finite or absurd link speed instead of failing the frame
- Network collection ignores a non-finite link speed instead of failing the sample
- Listing network interfaces returns an empty list when interface stats are unavailable
- CPU and memory panels tolerate a partial record instead of raising
- Byte formatters print zero for a non-finite or non-numeric size instead of `inf`, `nan`, or an exception
- CPU, memory, and network panels still draw when the section is not a record
- Brief mode and the terminal title tolerate a partial CPU, memory, network, or GPU record instead of raising
- GPU panels tolerate a partial record instead of raising
- NVIDIA collection keeps the GPUs it can read when one device query fails
- `sysmon network` and the network snapshot show packet counts, matching the dashboard
- `sysmon snapshot sensors` prints that same panel; the full snapshot includes it when the module is enabled
- `sysmon sensors` prints battery and temperatures, with the same JSON section as the other metric commands
- Sensor JSON includes `hottest_c`, the highest numeric temperature in the sample, including `sysmon brief --format json` and snapshots from the background collector. Prometheus exports it as `sysmon_temperature_hottest_celsius`
- `sysmon config show` prints the resolved configuration as JSON
- A broken `config.toml` reports the parser or value error before falling back to defaults
- Prometheus `/metrics` exports battery charge, remaining time when known, and sensor temperatures when they are present in the payload
- Prometheus `/metrics` exports per-mount disk utilization and per-interface network speeds when those lists are present
- Prometheus `/metrics` exports GPU memory and temperature alongside utilization
- Prometheus `/metrics` exports swap utilization and size when swap is present
- Prometheus `/metrics` exports aggregate disk read and write throughput, primary disk used, free, and total bytes, and the same byte sizes for each mount
- Prometheus `/metrics` exports network and disk byte totals as counters
- Prometheus `/metrics` exports memory used, available, and total bytes

### Changed
- The dashboard keeps sparklines for memory, disk read/write speed, and upload speed, next to the existing CPU and download history
- Sparklines fill missing history with the first real sample, so a short trail does not look like a jump up from zero
- Sparklines keep the newest sample on the right edge when the history is longer than the trail
- A sparkline with zero width returns an empty string instead of raising
- A history buffer with a non-positive length keeps one sample instead of raising
- Sparkline history drops NaN and infinite samples instead of crashing the dashboard
- Progress bars render `n/a` for NaN or infinite percentages instead of crashing the dashboard
- JSON metric status is `unknown` for a NaN or infinite percentage instead of `ok`
- JSON output replaces NaN and infinite numbers with null so one bad sample does not reject the whole document
- `sysmon serve` returns HTTP 500 JSON when a scrape fails, and later requests still succeed
- `sysmon serve` accepts a trailing slash on `/json`, `/metrics`, and `/health`
- `sysmon serve` answers HEAD with the same status and content length as GET, without a body
- Metrics responses send `Cache-Control: no-store` and always include a `sysmon_up` gauge and `sysmon_info` with the version label
- Prometheus `/metrics` exports `sysmon_collected_at_seconds` and `sysmon_sample_age_seconds` when the payload has `collected_at`
- Prometheus `/metrics` exports `sysmon_section_errors` when one or more sections failed
- The dashboard stays open when one frame fails to render and shows that error until the next successful frame
- The dashboard CPU panel still draws when the sample has no per-core list, and a non-record CPU sample shows the waiting panel
- `sysmon brief --watch` and `sysmon top --watch` stay open when one refresh fails and show that error
- The dashboard and `sysmon serve` reload `config.toml` when the file changes, without a restart
- `sysmon brief --watch` reloads thresholds and the selected network interfaces from `config.toml` on each frame
- `sysmon top --watch` reloads CPU and memory thresholds from `config.toml` on each frame
- The background collector keeps sampling after an unexpected collection error instead of stopping the thread
- The dashboard header says `stale` when the cached sample is older than three refresh intervals
- Dashboard history ignores a metric record that is missing its percent or speed instead of failing the whole frame
- `sysmon snapshot` and `sysmon serve` only sample network and disk counters when those modules are enabled. Snapshot also skips that wait for sections that do not need it
- The dashboard skips that same network and disk prime when those modules are disabled
- `sysmon snapshot` section names and `sysmon top --sort` accept any letter case
- JSON snapshots keep the sections that succeeded when one section raises, and record the failure under `errors`
- JSON snapshots, brief output, top output, and single-section JSON include `collected_at` as a Unix timestamp without changing `schema_version`. A snapshot built from the background collector uses that collector's timestamp, not the time the JSON was formatted
- JSON snapshots include `uptime_seconds` and `boot_time`, and Prometheus exports `sysmon_uptime_seconds` and `sysmon_boot_time_seconds`, when the boot time can be read
- Brief mode and the terminal title follow `[modules]` (and `enable_gpu`); a battery reading and the hottest temperature are included when sensors are enabled. Swap usage is appended only while swap is actually in use, and disk usage is appended only at or above the disk warn threshold
- Brief mode and the terminal title keep the rest of the line when swap or battery charge is missing or not a number
- Process memory percentages use the memory warn/critical thresholds. CPU bars still use the CPU thresholds
- The process table ignores rows that are not records instead of raising, and shows the empty state when none remain
- Process collection skips one unreadable process instead of failing the whole top list
- The native process list keeps the rows that are records when another row is not
- JSON process lists drop entries that are not records, including `sysmon top --format json` and snapshots from the background collector
- `sysmon brief --format json` uses those same module switches and includes `sensors` when the module is enabled

### Fixed
- Aggregate network collection returns zero counters instead of crashing when the OS exposes no I/O counters or the call raises. Disk I/O uses the same fallback, and usage for selected mounts is still reported
- A non-numeric disk byte counter is treated as zero instead of failing the disk sample
- Disk usage fields that are missing or not finite become zero instead of failing the sample
- CPU physical core count falls back to the logical count when the OS does not report it, instead of rendering "None cores"
- Uptime is 0 when the boot time is in the future, and "unknown" when the boot time cannot be read
- CPU collection returns a zero snapshot instead of crashing when percent sampling is not implemented
- Memory collection uses zero for a missing or non-finite field instead of failing the sample
- A non-numeric per-core sample or load average is dropped instead of failing the CPU snapshot
- CPU frequency is zero when the OS reports a missing or non-finite clock speed
- Memory collection keeps RAM data when swap is unavailable, and returns zeros instead of crashing when RAM itself cannot be read
- The native process scanner drops idle placeholders and the current process before applying the top-N limit, so the list is not shortened by those rows
- An unrecognized process sort key orders by CPU, matching the native scanner. It previously fell back to memory on the psutil path
- `get_top_processes(limit=None)` uses the default of 10 instead of raising
- Linux DRM GPUs are ordered by card number, so `card10` no longer sorts before `card2`
- Config intervals are clamped to 0.1–10 seconds, `process_limit` to 1–50, and a warn threshold above critical is swapped so the warning band still exists. A single string for `disk_mounts` or `network_interfaces` is kept as one entry instead of being split into characters. A non-table `modules` or `thresholds` value is ignored instead of discarding the rest of the file
- CI runs on `master` only
- Interactive `sysmon top --watch` treats `c`, `m`, `q`, and `/` as text while a name filter is being typed
- Interactive top reads keys during the refresh wait, so quit and filter typing are not stuck until the next sample
- A GPU temperature of 0°C is shown instead of being treated as missing
- An unreadable selected disk mount stays in the result at zero usage instead of being replaced by the primary disk
- Enumerating all disks skips virtual filesystems such as squashfs, tmpfs, and overlay. Explicit `disk_mounts` entries are still shown
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
