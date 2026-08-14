# SysMon

A beautiful system monitoring CLI tool built with Python.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- **Real-time Dashboard** - Live-updating terminal UI with CPU, Memory, Network, Disk, and GPU metrics
- **Snapshot Mode** - One-shot system info output with ASCII art logo
- **Brief Mode** - Single-line status display, perfect for terminal prompts
- **JSON Output** - Machine-readable output for scripts and automation
- **Disk Monitoring** - Disk usage and read/write I/O speeds
- **Configuration File** - Persistent defaults via `~/.config/sysmon/config.toml`
- **Real-time CPU Frequency** - Dynamic frequency detection using Windows Performance Counters
- **GPU Monitoring** - NVIDIA GPU utilization, VRAM, and temperature
- **Gradient Progress Bars** - Color-coded bars (green → yellow → red)
- **Per-core CPU View** - Individual core usage visualization
- **Multi-Disk / Multi-Network** - Monitor multiple mount points and per-interface network stats
- **Interactive Top** - Live process view with runtime sort and name filter
- **Background Collection** - Cached metric snapshots for smooth dashboard updates

## Installation

### Option 1: pip / pipx (Recommended)

```bash
pip install sysmon          # Core (CPU, memory, network, disk)
pip install sysmon[gpu]     # With NVIDIA GPU support
pipx install sysmon         # Global isolated install
```

From source:

```bash
pip install -e ".[dev]"     # Development
pip install -e ".[gpu]"     # With GPU extras
```

### Option 2: Standalone Executable (No Python required)

Download a prebuilt binary from [GitHub Releases](https://github.com/ider5/sysmon/releases):

- `sysmon-Windows.exe`
- `sysmon-Linux`
- `sysmon-macOS`

Or build it yourself from the repository root:

```bash
pip install -e ".[dev]"
python scripts/build_exe.py
```

The executable will be created as `dist/sysmon.exe` (Windows) or `dist/sysmon` (Linux/macOS).

## Usage

### Real-time Dashboard

```bash
sysmon                  # Launch real-time dashboard
sysmon dashboard        # Same as above
sysmon dashboard -r 2   # Refresh every 2 seconds
sysmon dashboard --no-gpu   # Hide GPU panel
```

Press `Ctrl+C` to exit the dashboard.

### Snapshot Mode

```bash
sysmon snapshot         # Show all system info with ASCII logo
sysmon snapshot cpu     # Show only CPU info
sysmon snapshot memory  # Show only memory info
sysmon snapshot network # Show only network info
sysmon snapshot disk    # Show only disk info
sysmon snapshot gpu     # Show only GPU info
sysmon snapshot process # Show only top processes
sysmon snapshot --format json   # JSON output for scripting
sysmon snapshot -s 0.5          # Faster network/disk speed sampling
sysmon snapshot --no-gpu        # Hide GPU section
```

### Individual Commands

```bash
sysmon cpu              # CPU details with per-core usage
sysmon memory           # Memory and swap usage
sysmon network          # Network speed and totals
sysmon disk             # Disk usage and I/O speeds
sysmon gpu              # GPU utilization, VRAM, temperature
sysmon top              # Top processes by CPU usage
sysmon top -n 15 --sort memory
sysmon top --watch      # Interactive: c/m sort, / filter, q quit
sysmon top --filter python
sysmon cpu --format json
```

### Shell Completion

```bash
# Bash (add to ~/.bashrc)
eval "$(sysmon --print-completion bash)"

# Zsh (add to ~/.zshrc)
eval "$(sysmon --print-completion zsh)"
```

Requires `pip install shtab` or `pip install -e ".[dev]"`.

### Configuration

```bash
sysmon config init      # Create ~/.config/sysmon/config.toml
sysmon config init --force  # Overwrite an existing config
sysmon config path      # Show config file location
```

Example `config.toml`:

```toml
refresh_interval = 1.0
sample_interval = 1.0
brief_refresh_interval = 2.0
enable_gpu = true
default_format = "rich"   # "rich" or "json" (CLI --format overrides)
process_limit = 10

# disk_mounts = ["C:\\", "D:\\"]       # omit = primary only; [] = all mounts
# network_interfaces = ["eth0"]        # omit = aggregate; [] = all interfaces

[modules]
cpu = true
memory = true
network = true
disk = true
gpu = true
process = true

[thresholds]
cpu_warn = 80
cpu_critical = 95
memory_warn = 80
memory_critical = 95
disk_warn = 80
disk_critical = 95
```

CLI flags override config values.

### Brief Mode (Single-line)

```bash
sysmon brief            # One-line status output
sysmon brief -w         # Watch mode (auto-refresh)
sysmon brief -w -r 2    # Watch mode, refresh every 2 seconds
sysmon brief -t         # Title mode (background, updates window title)
sysmon brief --stop     # Stop title mode
sysmon brief --no-color # No colors (for copy-paste)
sysmon brief --no-gpu   # Hide GPU info
sysmon brief --format json  # One-shot JSON (not with -w / -t)
```

Example output:
```
CPU 15% 3176M │ RAM 8.2/16.0G (51%) │ ↑1.2 MB/s ↓5.8 MB/s │ GPU 32% 2.1/10.0G 65°C
```

**Title Mode (`-t`)** runs as a background process and updates the terminal window title. Completely non-blocking - terminal is free to use immediately. Use `sysmon brief --stop` to stop.

> **Note:** VS Code's integrated terminal may not display title updates. For best results, use Windows Terminal or other standard terminal emulators.

### Other Options

```bash
sysmon --version        # Show version
sysmon --help           # Show help
```

## Output Example

### Snapshot Mode

```
   _____             __  __  ___
  / ___/__  _______  / / /  |/  /__
  \__ \/ / / / __ \/ / / /|_/ / _ \
 ___/ / /_/ / / / / / / /  / /  __/
/____/\__,_/_/ /_/_/ /_/  /_/\___/

  Host        cym
  OS          Windows 11
  Arch        AMD64
  Uptime      6h 9m

┌────────────────────────────────── 📊 CPU ───────────────────────────────────┐
│   Usage         ━━━━━━━━━━━━━━━━━━━━━━━━  85.3%                             │
│   Cores         14 cores / 20 threads                                        │
│   Frequency     3176 MHz                                                     │
└──────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────── 🎮 GPU ───────────────────────────────────┐
│   🎮 GPU 0: NVIDIA GeForce RTX 3060 Laptop GPU                              │
│   Utilization   ━━━━━━━━━━━━━━━━━━━━━━━  78.0%                              │
│   VRAM          ━━━━━━━━━━━━━━━━━━━━━━━  85.2%                              │
│   Temperature   🌡  72.0°C                                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Technical Details

### Real-time CPU Frequency

On Windows, `psutil.cpu_freq()` returns the base frequency, not the real-time frequency. SysMon uses Windows Performance Counters to get the actual dynamic frequency:

```
Real-time Frequency = Base Frequency × % Processor Performance / 100
```

A background daemon thread collects this data every 1.5 seconds, ensuring the UI remains responsive.

### Color Coding

Progress bars use configurable thresholds (`[thresholds]` in config; defaults warn=80, critical=95). Brief mode uses a simpler 60/80 split:

| Usage Level | Color |
|-------------|-------|
| Below warn (or under 60% in brief) | 🟢 Green |
| Warn range (or 60–80% in brief) | 🟡 Yellow |
| Critical (or 80%+ in brief) | 🔴 Red |

## Dependencies

| Library | Purpose |
|---------|---------|
| psutil | System metrics (CPU, Memory, Network, Disk) |
| Rich | Terminal UI (panels, tables, live display) |
| Typer | CLI framework |
| tomli | TOML parsing on Python < 3.11 (stdlib `tomllib` on 3.11+) |
| GPUtil / nvidia-ml-py | NVIDIA GPU monitoring (optional `[gpu]` extra) |
| shtab | Shell completion (optional; included in `[dev]`) |

## Publishing to PyPI

1. Create a GitHub Release (or run the **Publish PyPI** workflow manually).
2. Set repository secret `PYPI_API_TOKEN` with a PyPI API token.
3. The workflow runs tests, builds with `python -m build`, and uploads via `twine`.

Local build:

```bash
pip install build
python -m build
twine upload dist/*
```

## Development

```bash
pip install -e ".[dev]"
ruff check sysmon tests
pytest -v
```

## License

MIT
