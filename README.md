# grandma2-toolkit

Tools for **grandMA2 onPC v3.9.61**: a Python CLI (`ma2kit`) that drives the console over its Telnet
command line, plus (soon) Lua plugins that run inside it. Focus: effects, patching, and pan/tilt
normalization of moving heads.

> **Safety:** with an MA Command Wing or node connected, commands act on real fixtures. Develop
> against a throwaway show, and save your show before experimenting.

## Status

| Part | State |
|---|---|
| Telnet client, `doctor`, `cmd`, `shell` | working, tested offline and against onPC 3.9.61 |
| Show reader, plugin manager, utilities | planned, see [AGENT_BRIEF.md](AGENT_BRIEF.md) |

## Quick start (Windows, Python 3.11+)

1. In onPC: **Setup → Console → Global Settings → Telnet = Login Enabled**, and create an MA user for
   the tool (**Setup → Console → User & Profiles Setup**). Details: [docs/04-remote-control.md](docs/04-remote-control.md).
2. Install:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```
3. Configure: copy `config.example.toml` to `config.toml` and set the user and password.
   `config.toml` is git-ignored. Alternatively set the `MA2KIT_PASSWORD` environment variable.
4. Check the connection:
   ```powershell
   .\.venv\Scripts\ma2kit.exe doctor
   ```

## Commands

| Command | What it does |
|---|---|
| `ma2kit doctor` | Checks config, that onPC is reachable, Telnet is enabled, the login works, and the software version. |
| `ma2kit cmd "List Group"` | Sends one command line and prints the reply. |
| `ma2kit shell` | Interactive command line with the console's prompt. |
| `--dry-run` (global) | Prints what would be sent, sends nothing. |

`Delete`, `NewShow`, `LoadShow`, `Shutdown`/`Reboot`/`Restart` and anything with `/nc` ask for confirmation first
(`cmd --yes` skips it). Every command sent is appended to `logs/transcript.log`, with the password masked.

## Development

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Tests run offline against a fake console (`tests/fake_ma2.py`) that mimics the real Telnet greeting.

## Licence

MIT, see [LICENSE](LICENSE). grandMA2 is a product of MA Lighting; this project is not affiliated with it.
