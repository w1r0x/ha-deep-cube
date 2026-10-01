# BLE protocol of the deep.r sleep cube

Reverse-engineered on 2026-10-01 from the traffic between the deep up 1.5.5 app and a deep.r cube (firmware 1.8.9, hardware 1.0) and verified with the `tools/deep_cube.py` prototype.

The protocol is unofficial. Everything not confirmed by observation is marked as an assumption.

## Discovery and connection

- Advertised name: `deep.r` (the deep.n model is expected to advertise `deep.n`; not verified).
- The advertisement announces service `000000ff-0000-1000-8000-00805f9b34fb`; it is absent from the GATT table.
- The advertisement carries no state: it can only be read over an active connection.
- No pairing or encryption is required, MTU 244.
- The cube accepts a single connection. While a client is connected, the deep up app cannot connect, and vice versa.

## Services and characteristics

| Purpose | UUID | Properties |
| --- | --- | --- |
| Control service | `98658f38-e4e3-4ac4-8e14-b1b7ff024353` | |
| Status | `98658f39-e4e3-4ac4-8e14-b1b7ff024353` | read, notify |
| Commands | `98658f3a-e4e3-4ac4-8e14-b1b7ff024353` | write, notify |
| Settings service | `9b5bfb12-20d7-4730-aa0c-993ea99fd4cd` | |
| Settings | `9b5bfb13-20d7-4730-aa0c-993ea99fd4cd` | write, notify |
| Battery | `2a19` in service `180f` | read, percent |
| Power state | `2a1a` in service `180f` | read, `0x20` observed, meaning unknown |
| Device Information | `180a`: model `2a24`, firmware `2a26`, hardware `2a27`, manufacturer `2a29` | read |
| Firmware update | `f000ffc0-0451-4000-b000-000000000000` (`ffc1`, `ffc2`, `ffc5`) | **do not touch** |

## Program commands

Written to the command characteristic, always 8 bytes.

| Byte | Value |
| --- | --- |
| 0 | `0x1A` — start, `0x3C` — stop |
| 1 | program id |
| 2 | intensity: `0x00` — low, `0x7F` — normal, `0xFF` — maximum |
| 3 | program slot (see the program table; exact meaning unknown) |
| 4–7 | duration in seconds, uint32 LE |

Stop: `3c 00 00 00 00 00 00 00`.

The reply arrives as a notification on the same characteristic, 2 bytes:

| Reply | Meaning |
| --- | --- |
| `00 <id>` | start accepted |
| `00 00` | stopped |
| `04 00` | error; observed on stop when nothing was running |

An "accepted" reply does not guarantee that the program started: a 120-second start got `00 01`, but the program did not run. The result must be verified by reading the status.

The cube keeps advertising and accepts connections while a program is running, so a program can be started in one connection and stopped in another.

The cube has no notion of the time of day. The app converts the wake-up time into a duration counted from the moment of the start.

There are no separate pause and resume commands: pause is a stop, resume is a new start.

### Programs

| Program (name in the app) | Translation | id (byte 1) | slot (byte 3) |
| --- | --- | --- | --- |
| «Просто сон» | Just Sleep | `0x01` | 1 |
| «Сон медведя» | Bear Sleep | `0x0A` | 2 |
| «Дрим кит» | Dream Whale | `0x03` | 3 |
| «Ловец снов» | Dreamcatcher | `0x0B` | 4 |

The names were observed in the Russian interface of the app; the English names here are our own translation, not official ones.

The programs are built into the firmware. deep.r has other programs as well; their ids have not been observed.

## Status

Read or notification of the status characteristic, 12 bytes.

| Byte | Value |
| --- | --- |
| 0 | `0x00` — idle, `0xAA` — a program is running |
| 1 | program id |
| 2 | intensity of the running program; always `0x7F` when idle |
| 3 | `0x00` |
| 4–7 | total duration in seconds, uint32 LE |
| 8–11 | elapsed seconds, uint32 LE |

Idle: `00 00 7f 00 00000000 00000000`.

The elapsed counter is coarse. Observations:

- Duration 1800 s: notifications every ~1.8 s with elapsed 0, 1, 3, 5, 7, 9 — that is `floor(1.8 × k)`.
- Duration 72 530 s: one notification at the start (elapsed 0) and none in the following 10 s.
- Durations 58 982 s and 58 849 s: a read right after the start already returns 58; about a minute later it returns 117.

Assumption that fits all three: the counter advances in steps of 1/1000 of the duration, a notification is sent on each step, and the first step happens right after the start. The elapsed time is therefore accurate to about 0.1 % of the duration (roughly a minute for a night-long program).

## Settings

Exchange over the settings characteristic; replies arrive as notifications.

- Read: write `00 <id>`, reply `00 00 <id> <value>`.
- Write: write `<id> <value>`, reply `<id> 00`.
- Values: `0x1A` — on, `0x3C` — off.

| id | Setting |
| --- | --- |
| `0x01` | LED indication |
| `0x02` | "Turn off after 20 s" for the indication |
| `0x03` | vibration |
| `0x10` | read by the app on connect, reply `00 00 10` without a value; purpose unknown |

The intensity is not stored in the cube: the app remembers it and sends it in the start command.

## Unknown

- The exact meaning of byte 3 of the start command.
- The minimum accepted duration (between 2 and 30 minutes).
- Power state `2a1a` values while charging.
- The ids of the remaining deep.r programs and the behaviour of deep.n.
