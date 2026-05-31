# SysMon

A beautiful system monitoring CLI tool built with Python.

## Features

- **Real-time Dashboard** - Live-updating terminal UI with CPU, Memory, Network, and GPU metrics
- **Snapshot Mode** - One-shot system info output (neofetch style)
- **Per-module Views** - View individual metrics separately
- **GPU Support** - NVIDIA GPU monitoring via GPUtil
- **Cross-platform** - Works on Windows, macOS, and Linux

## Installation

### Option 1: pipx (Recommended for development)

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

### Real-time Dashboard (default)

```bash
sysmon                  # Launch real-time dashboard
sysmon dashboard        # Same as above
sysmon dashboard -r 2   # Refresh every 2 seconds
```

### Snapshot Mode

```bash
sysmon snapshot         # Show all system info
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
sysmon gpu              # GPU utilization and VRAM
```

### Other Options

```bash
sysmon --version        # Show version
sysmon --help           # Show help
```

## Dependencies

| Library | Purpose |
|---------|---------|
| psutil | System metrics (CPU, Memory, Network) |
| Rich | Terminal UI (panels, tables, live display) |
| Typer | CLI framework |
| GPUtil | NVIDIA GPU monitoring |

## License

MIT
