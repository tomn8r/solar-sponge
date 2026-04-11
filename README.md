# HA Solar Reserve

HA Solar Reserve is a Home Assistant integration that dynamically manages high-energy loads by predicting battery requirements. It analyzes historical consumption patterns and upcoming solar forecasts to determine if surplus energy can safely be used by "managed" appliances (e.g., AC units, pool heaters, or EV chargers) without compromising essential house operations.

## Core Functionality

The integration monitors the balance between available and required energy:

*   **Available Energy**: Current battery storage + remaining solar forecast for today.
*   **Required Energy**: Remaining house load for the current period (day/night) + tomorrow's projected solar deficit + emergency reserve.
*   **Permission**: A binary sensor (`binary_sensor.solar_reserve_permission`) toggles `on` when available energy exceeds the required threshold.

### Dynamic Load Modeling
The engine maintains a 7-day rolling average of house consumption, split into daytime and nighttime baselines.
- **Time Proration**: During the active period, the expected load is prorated based on time elapsed. This ensures a consistent reserve is maintained even if consumption exceeds the average early in the session.
- **Morning Dead-Zone Buffer**: A configurable time buffer (default 1.5 hours) allows the system to reserve enough energy to cover the gap between astronomical sunrise and functional solar generation.
- **36-Hour Lookahead**: If tomorrow's solar forecast is insufficient to cover tomorrow's expected loads, the engine will reserve additional capacity from today's battery/solar to cover the deficit.

## Features

- **Managed Load Isolation**: Link a specific energy sensor to exclude a device from your baseline. This prevents high-energy usage from inflating your reported "average" load.
- **Auto-Scaling**: Natively supports Wh, kWh, and MWh unit measurements.
- **Meter Flexibility**: Supports both perpetually cumulative energy meters and those that reset daily.
- **Resilient Logic**: Logic is calculated locally and persists across Home Assistant restarts.

## Configuration Requirements

The integration requires the following sensors:
1.  **Total Home Energy**: Cumulative house energy consumption (kWh/Wh).
2.  **Solar Forecast Today**: The remaining solar generation expected for the current day.
3.  **Solar Forecast Tomorrow**: The total solar generation expected for the next day.
4.  **Battery Sensor**: Current battery energy (kWh) or State of Charge (%).

## Installation

### HACS (Recommended)
1.  Open **HACS** in Home Assistant.
2.  Navigate to **Integrations** and select **Custom repositories** from the menu.
3.  Add this repository URL with the category `Integration`.
4.  Select **Download** and restart Home Assistant.

### Manual
1.  Copy the `custom_components/solar_reserve` directory into your Home Assistant `custom_components` folder.
2.  Restart Home Assistant.

## Setup

1.  Navigate to **Settings -> Devices & Services**.
2.  Click **Add Integration** and search for `HA Solar Reserve`.
3.  Complete the two-step configuration wizard. To adjust settings later (such as the Morning Buffer), click the **Configure** button on the integration card.

## Diagnostic Entities

The following entities are provided for automation and monitoring:
- `binary_sensor.solar_reserve_permission`: The primary state for automation triggers.
- `sensor.average_daytime_load`: Historical rolling average of house consumption during daylight.
- `sensor.average_overnight_load`: Historical rolling average of house consumption at night.
- `sensor.surplus_energy`: The calculated kWh difference between available and required energy.
- `sensor.energy_required`: The total calculated kWh reserve currently needed.
