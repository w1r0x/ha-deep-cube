# deep sleep cube for Home Assistant

**English** | [Русский](README.ru.md)

Unofficial Home Assistant integration for the deep sleep cube. Control is local, over Bluetooth LE, with no cloud and no manufacturer account.

The project is not affiliated with the device manufacturer. The protocol was recovered by observing the traffic between the author's own device and the official deep up app; see [docs/protocol.md](docs/protocol.md).

## Supported devices

| Model | Status |
| --- | --- |
| deep.r | Tested, firmware 1.8.9 |
| deep.n | Discovered and set up the same way, but **not tested**: the author has no such device. Please [open an issue](https://github.com/w1r0x/ha-deep-cube/issues) and tell how it works for you |

## Requirements

- Home Assistant 2025.2 or newer.
- A Bluetooth adapter or an [ESPHome Bluetooth Proxy](https://esphome.io/components/bluetooth_proxy.html) with active connections enabled, within range of the cube.

## Installation

### HACS (custom repository)

1. In HACS open the menu in the top right corner and choose **Custom repositories**.
2. Add `https://github.com/w1r0x/ha-deep-cube` with the type **Integration**.
3. Find **deep sleep cube** in HACS, download it and restart Home Assistant.

### Manual

Copy the `custom_components/deep_cube` folder into the `custom_components` folder of your Home Assistant configuration and restart Home Assistant.

## Setup

1. Close the deep up app on the phone: the cube accepts a single connection and is invisible while the app is connected.
2. Home Assistant finds the cube by itself and offers to add it in **Settings → Devices & services**. If it does not, press **Add integration** and choose **deep sleep cube**.

The polling interval (5 minutes by default) can be changed with the **Configure** button of the integration.

## Entities

| Entity | Type | Purpose |
| --- | --- | --- |
| *(device name)* | switch | The main switch of the cube: on starts the selected program until the wake-up time, off stops the running program |
| Program | select | Program for the next start |
| Wake-up time | time | The started program runs until the next occurrence of this time |
| Intensity | select | Intensity for the next start: low, normal or maximum. Hidden by default |
| Current program | sensor | The program that is running now, also when it was started from the app |
| Program end | sensor | When the running program ends |
| Battery | sensor | Battery level |
| LED indication | switch | Cube setting. Hidden by default |
| Turn indication off after 20 s | switch | Cube setting. Hidden by default |
| Vibration | switch | Cube setting. Hidden by default |

Entities hidden by default are rarely changed settings: they are available on the device page but do not appear on automatically generated dashboards. You can make them visible in the entity settings.

Program, wake-up time and intensity are kept in Home Assistant and are sent to the cube only when a program is started, the same way the official app does it.

Entity states do not depend on the interface language, so automations work in any language: programs are `just_sleep`, `bear_sleep`, `dream_whale`, `dreamcatcher`; intensities are `low`, `normal`, `max`.

## Actions

`deep_cube.start_program` starts a program in one call. Every parameter except the device is optional; omitted ones are taken from the entities above.

```yaml
action: deep_cube.start_program
data:
  device_id: <your cube>
  program: bear_sleep
  intensity: low
  wake_time: "07:30:00"
```

`deep_cube.stop_program` stops the running program.

```yaml
action: deep_cube.stop_program
data:
  device_id: <your cube>
```

## How it works and what to keep in mind

- The cube accepts one Bluetooth connection. The integration connects only for a poll or a command and disconnects right away, so the deep up app keeps working. While the app is connected to the cube, Home Assistant cannot reach it and the entities become unavailable until the next successful poll.
- The state is refreshed by polling, so changes made in the app or with the button on the cube show up with a delay of up to the polling interval. After a command from Home Assistant the state is read immediately.
- Four programs are supported: «Просто сон» (Just Sleep), «Сон медведя» (Bear Sleep), «Дрим кит» (Dream Whale) and «Ловец снов» (Dreamcatcher). The identifiers of other programs are not known yet. A program started from the app that the integration does not know is shown as "Other".
- The English program names are the author's translation and may differ from the official ones.
- The cube has no clock: the wake-up time is converted into a duration at the moment of the start.
- The cube silently ignores too short programs (2 minutes are ignored, 30 minutes work). The integration checks that the program has really started and reports an error if it has not.
- The end time is accurate to about 0.1 % of the program duration — roughly a minute for a night-long program.

## Languages

The interface is available in English and Russian and follows the language of your Home Assistant profile. To add a language, copy `custom_components/deep_cube/translations/en.json` to `<language code>.json`, translate the values and open a pull request. No code changes are needed.

## Troubleshooting

- **The cube is not found.** Close the deep up app, check that the cube is charged and within range of the adapter or proxy.
- **Entities are unavailable or commands fail with "Cannot reach the cube".** The signal is weak or the app holds the connection. Move the adapter or proxy closer.
- **Something else.** Download the diagnostics from the integration page and [open an issue](https://github.com/w1r0x/ha-deep-cube/issues). The diagnostics do not contain the address of the cube.

To see the exchange with the cube in the log:

```yaml
logger:
  logs:
    custom_components.deep_cube: debug
```

## Development

- [docs/protocol.md](docs/protocol.md) — BLE protocol description.
- [tools/](tools/) — debugging scripts for a PC built on `bleak`, including the control prototype `tools/deep_cube.py`.
- [changes/](changes/) — descriptions of completed changes.

The protocol module has no Home Assistant dependencies and is covered by tests:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-test.txt
.venv/Scripts/python -m pytest
```

## License

[MIT](LICENSE).
