# Braiins OS Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/v/release/drazi979/HASS-braiinsOS)](https://github.com/drazi979/HASS-braiinsOS/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![AI-Assisted](https://img.shields.io/badge/Development-AI--Assisted-blueviolet.svg)](#ai-assistance)

A custom integration for Home Assistant that lets you monitor and control a cryptocurrency miner running **Braiins OS**. It talks directly to the miner's local **REST API**, so no cloud service is needed.

It was built and tested on a water-cooled **Antminer S19e XP** (no fans), which is why it reports water inlet and outlet temperatures and has no fan sensors.

> **Disclaimer:** This is an unofficial community project and is not affiliated with Braiins. Changing power targets or other settings on mining hardware is done at your own risk.

## Features

- **Local control**: connects to your miner by its local IP address. No cloud account required.
- **Detailed monitoring**:
  * Hashrate (TH/s), power limit (W), current power consumption (W) and efficiency (J/TH).
  * Water inlet and water outlet temperature.
  * Chip temperature and per-hashboard temperatures.
  * Pool share sensors and a miner status sensor.
- **Controls**:
  * **Power target slider** with configurable minimum and maximum, in steps of 100 W.
  * **Pause / resume** switch for mining.
  * **Reboot** button.
- **Robust authentication**: the API token is refreshed before it expires, and Home Assistant shows a re-authentication prompt if the login ever stops working.
- **Configurable polling interval** in the integration options.
- **Branded look**: the integration ships with its own icon so it is easy to recognise in Home Assistant.

## Prerequisites

- A miner running **Braiins OS** with the REST API reachable on your network.
- Home Assistant **2026.9** or newer (developed and tested on 2026.9).
- [HACS](https://hacs.xyz/) installed (recommended).

## Installation

### HACS (recommended)

1. Open **HACS** in Home Assistant.
2. Click the three-dot menu in the top right and choose **Custom repositories**.
3. Paste this URL into the **Repository** field:

   ```
   https://github.com/drazi979/HASS-braiinsOS
   ```

4. Select **Integration** as the category and click **Add**.
5. Find **Braiins OS** in HACS and click **Download**.
6. Restart Home Assistant.

### Manual installation

1. Open the [latest release](https://github.com/drazi979/HASS-braiinsOS/releases/latest) page.
2. Download the source code (zip) and unzip it.
3. Copy the folder `custom_components/braiins_os` into your Home Assistant `config/custom_components/` directory.
4. Restart Home Assistant.

## Configuration

1. Go to **Settings** > **Devices & Services**.
2. Click **+ Add Integration** and search for **Braiins OS**.
3. Enter:
   - **Host**: the local IP address of your miner.
   - **Username** and **Password**: the same credentials you use for the Braiins OS web interface.
4. Click **Submit**.

The integration logs in and creates a device with all its entities.

### Options

Open the integration in **Devices & Services** and click **Configure** to change:

- **Polling interval**: how often the miner is queried.
- **Power target minimum / maximum**: the range of the power target slider. The values are rounded to multiples of 100 W (minimum rounded up, maximum rounded down). On an S19e XP the miner itself allows roughly 1249 W to 9900 W, so the slider range is 1300 W to 9900 W at most.

## Entities

| Entity | Type | Description |
| --- | --- | --- |
| Hashrate | Sensor | Current hashrate in TH/s. |
| Power limit | Sensor | The power limit the miner is currently running at, in W. |
| Power consumption | Sensor | Current power draw in W. |
| Efficiency | Sensor | Energy efficiency in J/TH. |
| Water inlet / outlet temperature | Sensor | Coolant temperatures in °C. |
| Chip temperature | Sensor | Chip temperature in °C, per hashboard where available. |
| Board temperature | Sensor | Per-hashboard temperature in °C. |
| Pool shares | Sensor | Accepted and rejected shares from the active pool. |
| Miner status | Sensor | Current state of the miner and its tuner. |
| Power target | Number (slider) | Sets the autotuning power target in W. |
| Mining | Switch | Pause and resume mining. |
| Reboot | Button | Reboots the miner. |

Entity names may differ slightly depending on your Home Assistant language and version.

## How the power target works

The power target you set in Home Assistant is the same value as the **Autotuning power target** in the Braiins OS web interface. The miner does not jump to that value at once. If **Dynamic Performance Scaling** is enabled, the tuner approaches the target in steps (for example 300 W per step), so the **Power limit** sensor follows the new target with a delay. This is normal behaviour of the miner, not a fault of the integration.

## Creating an energy sensor (kWh)

To track energy use in the Home Assistant **Energy dashboard**:

1. Go to **Settings** > **Devices & Services** > **Helpers**.
2. Create a **Riemann sum integral sensor**.
3. **Input sensor**: the power consumption sensor of this integration.
4. **Metric prefix**: `k` (kilo).
5. **Time unit**: `Hours`.
6. Use the resulting entity in your Energy dashboard.

## Version history

| Version | What it included / what changed |
| --- | --- |
| **0.3.0** | First working version. Connects to the Braiins OS REST API with automatic token refresh and a re-authentication prompt. Sensors for hashrate, power limit, power consumption, efficiency, water inlet/outlet temperature, chip and per-hashboard temperatures, pool shares and miner status. Pause/resume switch, reboot button, power target number (step 100 W, minimum rounded up and maximum rounded down to multiples of 100) and a configurable polling interval. Known issue: chip temperature sensors showed no values. |
| **0.3.1** | First version published on GitHub with HACS support. |
| **0.4.0 – 0.4.2** | Power target is now a slider with configurable minimum and maximum. Added brand images (icon) so the integration is recognisable in Home Assistant. Improved behaviour with Dynamic Performance Scaling, where the tuner reaches the target step by step. Repository cleanup for HACS validation (manifest, topics, hacs.json). |

See the [releases page](https://github.com/drazi979/HASS-braiinsOS/releases) for the full notes of each version.

## Known issues

- **Tuner status wording**: the raw tuner state `3` is shown as "tuning" in Home Assistant, while the Braiins OS web interface shows "Running" for the same state. The "preheat" state has not been verified yet.
- **Power limit lag**: with Dynamic Performance Scaling enabled, the power limit sensor reaches a new target only after several tuner steps (see [How the power target works](#how-the-power-target-works)).
- Tested only on an Antminer S19e XP. Other models should work through the same API but have not been verified.

## AI Assistance

This integration was developed with the assistance of Artificial Intelligence tools.

## Contributing

Bug reports and suggestions are welcome. Please open an issue on the [issues page](https://github.com/drazi979/HASS-braiinsOS/issues) and include your Home Assistant version, your Braiins OS version and the relevant log lines (remove IP addresses, passwords and tokens first).

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
