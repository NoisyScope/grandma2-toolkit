# Remote control of grandMA2 onPC over Telnet

Each statement is marked **verified on 3.9.61** (observed on a running onPC) or **unverified** (from
general grandMA2 knowledge; to be confirmed).

## Ports

- **verified** onPC listens on all network interfaces on TCP 80, 7001, 7003, 7005, 30000 and 30001.
- **verified** **30000** is the remote command line. **30001** streams the system monitor log without any
  login (useful for debugging plugins, since `gma.echo` output shows up there).
- **unverified** 80 is the web remote; 7001–7005 are MA-Net session traffic. Not used by this toolkit.

## Enabling it

1. **Setup → Console → Global Settings → Telnet**: change **Disabled** to **Login Enabled**. No restart needed.
2. **Setup → Console → User & Profiles Setup**: add a user for the toolkit (e.g. `toolkit`) with a password
   and its own user profile, so the tool has its own programmer and command line.

Because onPC listens on every interface, anyone on the same network can reach port 30000 once Telnet is
enabled. Use a real password and turn Telnet off on untrusted show networks.

## What the console sends (verified)

| Situation | Reply on port 30000 |
|---|---|
| Telnet disabled | `Remote commandline disabled`, then the connection closes |
| Telnet = Login Enabled | ASCII-art "MA" banner, `Logged in as User 'guest'`, then ` [Group]>Please login !` and ` [Group]>` |

- Lines end with `\r\n` or `\n\r`, mixed, and contain ANSI colour codes.
- At the root of the object tree the prompt is `[<default keyword>]>`, e.g. `[Group]>` or `[Channel]>`.
  After `cd` into the tree it is the path followed by ` >`, e.g. `EditSetup/Layers 4/PAR_LED 3 >`.
  `ma2kit` recognises both. The `cd` location belongs to the Telnet session: a new login starts at the root.

## Logging in (verified)

`Login "user" "password"`. On success the reply contains `Logged in as User 'user'`. An unknown user
replies `Error #72: COMMAND NOT EXECUTED`; `ma2kit` treats any reply without the "Logged in" line as a failed
login. Quotes inside the name or password are not supported.

## Reply format (verified)

```
Executing : List Group
        No.  Name         Info
Group 1 1    ALL
Group 2 2    PAR_ALL
```

- Every reply starts with `Executing : <command>`; `ma2kit` removes this echo line.
- A reply ends with a blank line, a line holding a single space, then the prompt.
- A failed command adds `Error : <command>` and `Error #<n>: <MESSAGE>`, for example
  `Error #14: OBJECT DOES NOT EXIST` (`List Nonsense`).

## Useful read-only commands (verified)

- `ListVar` prints every system variable as `Global : $NAME = value`, including `$VERSION` (e.g. `3.9.61.5`),
  `$SHOWFILE` (loaded show), `$USER`, `$USERRIGHTS`, `$HOSTSTATUS` (`Standalone` when not in a session),
  `$PATH`, `$PLUGINPATH`, `$TEMPPATH`, `$SELECTEDFIXTURESCOUNT`, `$SELECTEDEXEC`, `$FADERPAGE`, `$BUTTONPAGE`.
  `ma2kit doctor` uses it for the version and loaded-show checks.
- `List Group` lists the group pool: `Group <id> <no>  <name>`.

- The echo normalises keywords: `Lua "..."` is echoed as `Executing : LUA "..."`.

## Output after the prompt (verified)

Some commands return to the prompt before they finish. `Plugin N` prints the prompt at once; the plugin's
`gma.feedback()` text arrives later, right after the prompt: ` [Group]>MA2KIT_PROBE feedback`. The one-line
`Lua "..."` command behaves the same way. `ma2kit` keeps such text in `CommandResult.late`, can wait for
a marker with `MA2Client.wait_for()`, and returns anything that arrives later with `MA2Client.poll()`
(batch runs print it under the step that caused it).

## Confirmation dialogs (verified)

```
ATTENTION: Please confirm! : Reload plugin engine ? :
[1]: Ok
 2 : Cancel
```

```
Overwrite Confirmation : At the import destination already exists object "ma2kit_info 100". :
[1]: Overwrite
 2 : Overwrite|All
 3 : Insert
 4 : Insert|All
 5 : Cancel
```

The default option is in brackets. The console waits until an option number is sent and replies
` - Selected <label>`, then the prompt. `/nc` on a command skips the dialog. `ma2kit` answers Cancel unless
a handler (or the person in `shell`) picks another option.

## How `ma2kit` decides a reply is complete

There is no end-of-reply marker. After sending, the client looks for the command's echo, then for a prompt
after it (or a dialog), and returns once no new data arrives for 0.3 s; it fails after the configured
timeout (5 s default). Output that arrives between commands is logged to the transcript as unsolicited.
If the console closed the connection, the next command reconnects and logs in again; a command is only
resent when it certainly never reached the console.
