# Install and set up

From a clean checkout to a working `ma2kit` on Windows with grandMA2 onPC 3.9.61.

## 1. What you need

- grandMA2 onPC **3.9.61** running on the same PC (other versions are untested; `ma2kit doctor` warns).
- Python **3.11 or newer** (developed on 3.12). No other packages are needed to run it.
- Git, to clone the repository.
- Optional: a test show you can change freely. Everything below works on any show, but keep tests away
  from your real shows (see step 5).

## 2. Turn on the remote command line in onPC

These are console settings, so only you change them; ma2kit never does.

1. In onPC, press **Setup**.
2. Under **Console**, open **Global Settings**.
3. Set **Telnet** to **Login Enabled**. No restart is needed.

✔ Before this, port 30000 answers `Remote commandline disabled` and closes; afterwards it greets with the
MA banner and `Please login !`. onPC listens on every network interface, so anyone on your network can
reach it: use a real password (next step) and set Telnet back to **Disabled** on networks you do not trust.

## 3. Create a user for the toolkit

1. **Setup → Console → User & Profiles Setup**.
2. Add a user, e.g. `toolkit`, give it a password, and pick its rights. The toolkit was tested with
   **Admin** rights (needed to import plugins and macros; lower rights are untested).
3. Give it its own user profile if you like, so its programmer and command line stay separate from yours.

✔ `List User` over Telnet shows the users and their rights (passwords appear as `*****`).

## 4. Install ma2kit

```powershell
git clone https://github.com/NoisyScope/grandma2-toolkit.git
cd grandma2-toolkit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

`[dev]` adds pytest for the offline tests. Without activating the virtual environment, run the tool as
`.\.venv\Scripts\ma2kit.exe`.

## 5. Configure

```powershell
copy config.example.toml config.toml
```

Edit `config.toml` (it is git-ignored, never commit it):

| Setting | What to put |
|---|---|
| `[console] user`, `password` | The user from step 3. Or leave `password` empty and set the `MA2KIT_PASSWORD` environment variable |
| `[console] host`, `port` | `127.0.0.1` and `30000` for onPC on this PC |
| `[safety] allowed_shows` | Names of shows ma2kit may change, e.g. `["toolkit_dev"]`. Empty means any show; set it while you experiment |
| `[pools]` | First pool numbers ma2kit uses for groups (500), plugins (100), macros (500) |
| `[backup]` | Where `ma2kit backup` keeps show copies, and how many |

`MA2KIT_CONFIG` can point to a config file somewhere else.

## 6. Check everything

```powershell
.\.venv\Scripts\ma2kit.exe doctor
```

A healthy result:

```
[OK  ] config file: ...\grandma2-toolkit\config.toml
[OK  ] password set: yes
[OK  ] console reachable: 127.0.0.1:30000
[OK  ] system monitor: 127.0.0.1:30001
[OK  ] Telnet enabled: greeted as 'guest', prompt [Group]
[OK  ] login: logged in as 'toolkit'
[OK  ] software version: 3.9.61.5
[OK  ] user rights: Admin
[OK  ] loaded show: <your show> (may be changed)
[OK  ] plugin folder: C:/ProgramData/MA Lighting Technologies/grandma/gma2_V_3.9.61/plugins
[OK  ] temporary export files: none left over
```

Then open the menu with `.\.venv\Scripts\ma2kit.exe`, or see the [README](../README.md) for all commands.

## 7. First steps

```powershell
ma2kit backup                      # save the show and keep a copy
ma2kit show summary                # what is in the show
ma2kit plugins install ma2kit_info # put the example plugin in the show
ma2kit plugins run ma2kit_info
```

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `console reachable: FAIL` | onPC is not running, or `host`/`port` are wrong |
| `Telnet is disabled on the console` | Step 2 |
| `login: FAIL` | Wrong user or password; the console answers `Error #72: COMMAND NOT EXECUTED`. Check `List User` on the console |
| `loaded show: ... (NOT in allowed_shows: read-only)` | Show-changing commands are refused on this show. Load the test show or add it to `allowed_shows` |
| `no prompt after 5.0s` | The console is busy (loading a show) or a dialog is open on its screen. Close the dialog; raise `timeout` if it happens with long commands |
| A plugin seems to do nothing | Its output goes to the command line and to the system monitor: `ma2kit monitor` shows `gma.echo` output and Lua errors |
| An edited plugin still runs the old code | The show stores a copy: run `ma2kit plugins update <name>` |
| A plugin hangs | It is waiting in a dialog (`gma.gui.confirm`, `gma.textinput`) on the onPC screen |
| `temporary export files` listed | An earlier run was interrupted; `doctor` removes them |

## Running the tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

They run offline against a fake console (`tests/fake_ma2.py`) that copies the replies captured on 3.9.61.
