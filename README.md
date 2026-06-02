# SysMon

A beautiful system monitoring CLI tool built with Python.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- **Real-time Dashboard** - Live-updating terminal UI with CPU, Memory, Network, and GPU metrics
- **Snapshot Mode** - One-shot system info output with ASCII art logo
- **Brief Mode** - Single-line status display, perfect for terminal prompts
- **Real-time CPU Frequency** - Dynamic frequency detection using Windows Performance Counters
- **GPU Monitoring** - NVIDIA GPU utilization, VRAM, and temperature
- **Gradient Progress Bars** - Color-coded bars (green → yellow → red)
- **Per-core CPU View** - Individual core usage visualization
- **Background Collection** - Non-blocking metric collection for smooth UI

## Installation

### Option 1: pipx (Recommended)

```bash
# Install pipx if not installed
pip install pipx
pipx ensurepath

# Install sysmon globally
pipx install ./sysmon
```

After installation, `sysmon` command is available globally without activating any environment.

### Option 2: Standalone Executable (No Python required)

Download `sysmon.exe` from the `dist/` folder and run it directly.

Or build it yourself:

```bash
cd sysmon
python build.py
```

The executable will be created in `dist/sysmon.exe`.

### Option 3: pip install (in a virtual environment)

```bash
cd sysmon
pip install -e .
```

## Usage

### Real-time Dashboard

```bash
sysmon                  # Launch real-time dashboard
sysmon dashboard        # Same as above
sysmon dashboard -r 2   # Refresh every 2 seconds
```

Press `Ctrl+C` to exit the dashboard.

### Snapshot Mode

```bash
sysmon snapshot         # Show all system info with ASCII logo
sysmon snapshot cpu     # Show only CPU info
sysmon snapshot memory  # Show only memory info
sysmon snapshot network # Show only network info
sysmon snapshot gpu     # Show only GPU info
```

### Individual Commands

```bash
sysmon cpu              # CPU details with per-core usage
sysmon memory           # Memory and swap usage
sysmon network          # Network speed and totals
sysmon gpu              # GPU utilization, VRAM, temperature
```

### Brief Mode (Single-line)

```bash
sysmon brief            # One-line status output
sysmon brief -w         # Watch mode (auto-refresh)
sysmon brief -w -r 2    # Watch mode, refresh every 2 seconds
sysmon brief -t         # Title mode (non-intrusive, updates window title)
sysmon brief --no-color # No colors (for copy-paste)
sysmon brief --no-gpu   # Hide GPU info
```

Example output:
```
CPU 15% 3176M │ RAM 8.2/16.0G (51%) │ ↑1.2 MB/s ↓5.8 MB/s │ GPU 32% 2.1/10.0G 65°C
```

**Title Mode (`-t`)** updates the terminal window title without affecting terminal content. Perfect for monitoring while working.

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

| Usage Level | Color |
|-------------|-------|
| 0-60% | 🟢 Green |
| 60-80% | 🟡 Yellow |
| 80-100% | 🔴 Red |

## Dependencies

| Library | Purpose |
|---------|---------|
| psutil | System metrics (CPU, Memory, Network) |
| Rich | Terminal UI (panels, tables, live display) |
| Typer | CLI framework |
| GPUtil | NVIDIA GPU monitoring |

## License

MIT
