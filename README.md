# HA Solar Reserve

A highly advanced, dynamic Home Assistant custom integration designed to intelligently manage high-energy loads (like a "Solar Sponge" AC system) based on real-time solar forecasts and rolling historical energy usage.

Instead of relying on arbitrary static battery reserves, Solar Sponge uses a **36-Hour Predictive Engine** to automatically calculate exactly how much battery power you need to survive tonight and tomorrow, guaranteeing your battery is never unnecessarily depleted by thirsty smart appliances.

## Features

- **36-Hour Predictive Engine**: Dynamically calculates the deficit between tomorrow's expected solar harvest and your next 24-hours of expected house load. It adjusts your battery reserve in real-time.
- **Symmetrical Load Tracking**: Automatically tracks the exact amount of energy your house uses between Sunrise and Sunset (Day Load) and Sunset and Sunrise (Night Load).
- **AC Baseline Isolation**: Optionally specify your AC's dedicated Energy Sensor. The integration mathematically isolates it from your Total Home Energy so that running the AC doesn't create a false feedback loop inflating your baseline averages.
- **Unit Auto-Scaling**: Flawlessly supports `Wh`, `kWh`, and `MWh` sensors natively, auto-scaling them behind the scenes.
- **Dynamic Configuration (Options Flow)**: Tweak your Emergency Reserve, change your Battery definitions, or swap out sensors on the fly without deleting the integration.
- **Legacy Meter Support**: The mathematical engine seamlessly handles both perpetually cumulative energy meters and legacy meters that reset to zero at midnight.

## Requirements

To use this integration, you must have the following entities available in Home Assistant:
1. **Total Home Energy Sensor**: A cumulative energy sensor (kWh).
2. **Solar Forecast Sensors**: Two sensors detailing your Solar Forecast Remaining Today and Solar Forecast Tomorrow.
3. **Battery Sensor**: A sensor detailing your battery's current state of charge (either in kWh or %).
4. **sun.sun**: The native Home Assistant sun tracker must be enabled.

## Installation

### Method 1: HACS (Recommended)
1. Open Home Assistant and navigate to **HACS**.
2. Click **Integrations** -> **Custom repositories** (three dots in top right).
3. Add the URL to this repository and select `Integration` as the category.
4. Click **Download** and restart Home Assistant.

### Method 2: Manual Installation
1. Download the `solar_sponge` folder from the `custom_components` directory in this repository.
2. Copy the folder to your Home Assistant `custom_components` directory (`/config/custom_components/solar_sponge`).
3. Restart Home Assistant.

## Configuration

1. Navigate to **Settings -> Devices & Services**.
2. Click **+ Add Integration** and search for `HA Solar Reserve`.
3. Follow the two-step wizard to map your energy inputs and battery constraints.

### Understanding the 36-Hour Deficit Calculation
The core of the integration is measuring `Surplus`. Specifically:
`Available Energy = (Current Battery Energy + Solar Remaining Today)`
`Required Energy = (Expected Load Tonight + Tomorrow's Deficit + Emergency Reserve)`

`Tomorrow's Deficit` asks the question: *Is tomorrow's Solar forecast enough to cover my house's average Daytime and Nighttime usage for the following 24 hours?* If the answer is no, it holds the difference back in the battery tonight to guarantee survival.

If `(Available Energy - Required Energy)` is greater than 0, the exposed `binary_sensor.solar_reserve_permission` turns `on`!

## Exposed Sensors
The integration automatically creates several sensors under its registered **HA Solar Reserve** device:
- `binary_sensor.solar_reserve_permission`: The master switch used to automate your appliances.
- `sensor.overnight_load_tracker`: Your true baseline energy used during the current/last night.
- `sensor.daytime_load_tracker`: Your true baseline energy used during the current/last day.
- `sensor.average_overnight_load`: The 7-day rolling average of your overnight load.
- `sensor.average_daytime_load`: The 7-day rolling average of your daytime load.
