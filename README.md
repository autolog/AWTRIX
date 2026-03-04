# AWTRIX 3 Plugin for Indigo

An [Indigo](https://www.indigodomo.com/) plugin for controlling [AWTRIX 3](https://github.com/Blueforcer/awtrix3) LED matrix clocks (such as the Ulanzi TC001) via MQTT.

## Requirements

- **Indigo 2025.1** or later
- **MQTT broker** (e.g. Mosquitto) accessible on your network
- **Ulanzi TC001** (or compatible device) running [AWTRIX 3 firmware](https://blueforcer.github.io/awtrix3/)

The plugin automatically installs its Python dependencies (`paho-mqtt`, `cryptography`) when first loaded.

## Installation

1. Download the latest release from the [Releases](../../releases) page
2. Double-click `AWTRIX.indigoPlugin` to install in Indigo
3. Enable the plugin when prompted

## Setup

### 1. Create an AWTRIX Coordinator

The coordinator manages the MQTT broker connection. You need one coordinator per MQTT broker.

1. Go to **Devices > New...** and select **Type: AWTRIX 3**
2. Select **Model: AWTRIX Coordinator**
3. Configure the MQTT broker connection:
   - **MQTT Broker IP** - your broker's IP address
   - **MQTT Broker Port** - typically `1883`
   - **MQTT Username / Password** - if your broker requires authentication (password is encrypted at rest)
   - **MQTT Client Prefix** - unique prefix for the MQTT client ID (default: `indigo_awtrix`)
   - **MQTT Protocol** - MQTTv311 (default) or MQTTv31

### 2. Create an AWTRIX Clock

Each clock device represents one physical AWTRIX device.

1. Go to **Devices > New...** and select **Type: AWTRIX 3**
2. Select **Model: AWTRIX Clock**
3. Configure:
   - **AWTRIX Coordinator** - select the coordinator created above
   - **AWTRIX MQTT Prefix** - the MQTT prefix configured on your AWTRIX device (e.g. `awtrix_XXXXXX`). You can find this in the AWTRIX web interface under MQTT settings.

Once created, the clock device will show as **connecting ...** until it receives its first stats update from the AWTRIX device (typically within a few seconds). If the device doesn't come online, check that the MQTT prefix matches exactly.

## Device Controls

The clock device appears as a **dimmer** in Indigo, giving you native on/off and brightness control:

- **Turn On / Turn Off** - powers the AWTRIX display on or off
- **Set Brightness** - adjusts display brightness (0-100%, mapped to 0-255 on the device)
- **Brighten By / Dim By** - relative brightness adjustments

These controls work from the Indigo client, UI+ app (Mac and iOS), and Control Pages.

## Device States

The clock device exposes the following states for use in triggers, conditions, and Control Pages:

| State | Description |
|-------|-------------|
| `status` | Connection status |
| `onOffState` | Power state |
| `brightnessLevel` | Current brightness (0-100) |
| `battery` | Battery level % |
| `temperature` | Onboard sensor temperature |
| `humidity` | Onboard sensor humidity |
| `wifiSignal` | WiFi signal strength (RSSI) |
| `currentApp` | Currently displayed app name |
| `firmwareVersion` | AWTRIX firmware version |
| `uid` | Device unique identifier |
| `freeRam` | Free RAM in bytes |
| `uptime` | Device uptime in seconds |
| `messageCount` | MQTT message count |
| `lastStatsTime` | Timestamp of last stats update |
| `lastButtonPress` | Last physical button pressed (`buttonLeft`, `buttonMiddle`, `buttonRight`) |
| `indicator1Active` | Indicator 1 on/off |
| `indicator2Active` | Indicator 2 on/off |
| `indicator3Active` | Indicator 3 on/off |

### Offline Detection

The plugin monitors stats updates from each clock. If no stats are received for 60 seconds, the device is marked as **offline**. It automatically recovers when stats resume.

### Button Presses

Physical button presses on the Ulanzi TC001 (left, middle, right) update the `lastButtonPress` state. You can create Indigo triggers on this state to respond to button events.

## Actions

All actions are available under **Device Actions** when configuring Action Groups, Triggers, or Schedules for an AWTRIX Clock device. Each action can also be called from scripts using `executeAction()` with the action ID and props shown below.

### Send Notification

Display a temporary notification on the clock.

**Action ID:** `sendNotification`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `text` | string | `""` | Message to display |
| `icon` | string | `""` | Icon ID from the [AWTRIX icon database](https://developer.lametric.com/icons) or filename |
| `color` | string | `""` | Text colour in hex (e.g. `#FF0000`) |
| `duration` | string | `"5"` | Display time in seconds |
| `sound` | string | `""` | RTTTL sound filename from the device's MELODIES folder |
| `hold` | bool | `False` | Hold notification on screen until explicitly dismissed |
| `rainbow` | bool | `False` | Cycle text through rainbow colours |

### Dismiss Notification

Dismiss a held notification. No props required.

**Action ID:** `dismissNotification`

### Navigate App

Switch to the next or previous app in the app loop.

**Action ID:** `navigateApp`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `direction` | string | `"next"` | `"next"` or `"previous"` |

### Update Custom App

Create or update a custom app that appears in the app loop.

**Action ID:** `updateCustomApp`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `appName` | string | **required** | Unique app name (no spaces) |
| `text` | string | `""` | Text to display |
| `icon` | string | `""` | Icon ID or filename |
| `color` | string | `""` | Text colour (hex) |
| `duration` | string | `""` | Display duration in seconds |
| `lifetime` | string | `"0"` | Auto-remove after N seconds without update (0 = never) |
| `rainbow` | bool | `False` | Rainbow text effect |
| `noScroll` | bool | `False` | Disable text scrolling |
| `progress` | string | `"-1"` | Progress bar value 0-100 (-1 = off) |
| `progressC` | string | `""` | Progress bar colour (hex) |

### Remove Custom App

Remove a custom app from the app loop by name.

**Action ID:** `removeCustomApp`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `appName` | string | **required** | App name to remove |

### Set Indicator

Set one of three coloured indicator dots on the right side of the display.

**Action ID:** `setIndicator`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `indicatorNumber` | string | `"1"` | `"1"` (upper right), `"2"` (right side), `"3"` (lower right) |
| `color` | string | `"#FF0000"` | Indicator colour (hex) |
| `blink` | string | `"0"` | Blink interval in ms (0 = off) |
| `fade` | string | `"0"` | Fade interval in ms (0 = off) |

### Clear Indicator

Turn off an indicator dot.

**Action ID:** `clearIndicator`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `indicatorNumber` | string | `"1"` | `"1"`, `"2"`, or `"3"` |

### Switch to App

Jump directly to a specific app by name.

**Action ID:** `switchApp`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `appName` | string | **required** | Built-in: `Time`, `Date`, `Temperature`, `Humidity`, `Battery`. Or your custom app name. |

### Play Sound

Play a sound on the device's buzzer.

**Action ID:** `playSound`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `soundType` | string | `"file"` | `"file"` (RTTTL filename from MELODIES folder) or `"rtttl"` (inline RTTTL string) |
| `sound` | string | **required** | Filename (without extension) or full RTTTL string |

### Set Mood Light

Turn the entire LED matrix into a coloured background light.

**Action ID:** `setMoodLight`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `moodMode` | string | `"color"` | `"color"`, `"kelvin"`, or `"off"` |
| `brightness` | string | `"170"` | Brightness 0-255 (colour and kelvin modes) |
| `moodColor` | string | `"#FFFFFF"` | Colour hex (colour mode only) |
| `kelvin` | string | `"2300"` | Colour temperature (kelvin mode only) |

### Update Settings

Change device settings without using the AWTRIX web interface. Only include the settings you want to change. Leave props as empty string or `"unchanged"` to skip them.

**Action ID:** `updateSettings`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `ATIME` | string | `""` | App display duration (seconds) |
| `ATRANS` | string | `"unchanged"` | Auto app switching: `"true"`, `"false"`, or `"unchanged"` |
| `TEFF` | string | `"unchanged"` | Transition effect 0-10, or `"unchanged"` |
| `TSPEED` | string | `""` | Transition speed (ms) |
| `SSPEED` | string | `""` | Scroll speed (%) |
| `TCOL` | string | `""` | Global text colour (hex) |
| `UPPERCASE` | string | `"unchanged"` | Force uppercase: `"true"`, `"false"`, or `"unchanged"` |
| `ABRI` | string | `"unchanged"` | Auto brightness: `"true"`, `"false"`, or `"unchanged"` |
| `CEL` | string | `"unchanged"` | Celsius: `"true"`, Fahrenheit: `"false"`, or `"unchanged"` |
| `VOL` | string | `""` | Volume 0-30 |

### Sleep

Put the device to sleep for a specified duration. The device wakes automatically when the timer expires, or when the middle button is pressed. Use **Turn Off** for indefinite power off.

**Action ID:** `sleepDevice`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `sleepSeconds` | string | `"3600"` | Sleep duration in seconds |

### Reboot Device

Reboot the AWTRIX device. No props required.

**Action ID:** `rebootDevice`

### Send Raw MQTT JSON

Send any MQTT message to the device for advanced use cases not covered by the built-in actions.

**Action ID:** `sendRawJson`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `topicSuffix` | string | **required** | Topic suffix appended to the device's MQTT prefix (e.g. `notify`, `settings`, `custom/myapp`) |
| `payload` | string | `""` | Valid JSON string, or leave empty for topics that require no payload |

## Variable Substitution

All text fields in actions support [Indigo variable substitution](https://wiki.indigodomo.com/doku.php?id=indigo_2025.1_documentation:plugins:variable_substitution) markup:

| Markup | Description | Example |
|--------|-------------|---------|
| `%%v:VARID%%` | Indigo variable value | `%%v:12345%%` |
| `%%d:DEVID:STATEID%%` | Device state value | `%%d:67890:temperature%%` |
| `%%t:"FORMAT"%%` | Formatted timestamp | `%%t:"%H:%M"%%` |

For example, a notification text of `Indoor: %%d:67890:temperature%%F` would resolve at runtime to something like `Indoor: 72.5F`.

## Scripting

All plugin actions are scriptable from Indigo's built-in Python scripting:

```python
awtrix = indigo.server.getPlugin("com.autologplugin.indigoplugin.awtrix3")
if awtrix.isEnabled():
    awtrix.executeAction("sendNotification", deviceId=12345, props={
        "text": "Hello from a script!",
        "icon": "2056",
        "color": "#FF0000",
        "duration": "10"
    })
```

Available action IDs: `sendNotification`, `dismissNotification`, `navigateApp`, `updateCustomApp`, `removeCustomApp`, `setIndicator`, `clearIndicator`, `switchApp`, `playSound`, `sendRawJson`, `setMoodLight`, `updateSettings`, `sleepDevice`, `rebootDevice`

Refer to the action descriptions above for the complete list of available props for each action.

## Compatibility

- **Indigo**: 2025.1 or later (Server API 3.7)
- **macOS**: Compatible with all macOS versions supported by Indigo 2025.1
- **AWTRIX Firmware**: AWTRIX 3 (tested with recent releases)
- **MQTT**: v3.1 and v3.11

## Support

- [AWTRIX 3 Documentation](https://blueforcer.github.io/awtrix3/)
- [Indigo Domotics Forum](https://forums.indigodomo.com/viewforum.php?f=420)

## License

This project is licensed under the [MIT License](LICENSE). Copyright &copy; 2026 Autolog.
