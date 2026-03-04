#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# AWTRIX 3 - Plugin © Autolog 2026
#

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

import json
import logging
import queue
import sys
import time
import threading
import traceback
from datetime import datetime

from constants import *


# noinspection PyPep8Naming
class ThreadAwtrixHandler(threading.Thread):

    # This class handles AWTRIX message processing

    def __init__(self, pluginGlobals, event, coordinator_dev_id):
        try:
            threading.Thread.__init__(self)

            self.globals = pluginGlobals
            self.coordinator_dev_id = coordinator_dev_id

            self.awtrixLogger = logging.getLogger("Plugin.AWTRIX")

            self.threadStop = event

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method} [{self.globals[PLUGIN_INFO][PLUGIN_VERSION]}]'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.awtrixLogger.error(log_message)

    def run(self):
        try:
            while not self.threadStop.is_set():
                try:
                    mqtt_message_sequence, process_command, coordinator_dev_id, awtrix_prefix, topic, payload = \
                        self.globals[QUEUES][AWTRIX_QUEUE][self.coordinator_dev_id].get(True, 5)

                    if process_command == HANDLE_AWTRIX_STATS:
                        self.handle_stats(awtrix_prefix, payload)
                    elif process_command == HANDLE_AWTRIX_EFFECTS_LIST:
                        self.handle_effects_list(awtrix_prefix, payload)
                    elif process_command == HANDLE_AWTRIX_TRANSITIONS_LIST:
                        self.handle_transitions_list(awtrix_prefix, payload)
                    elif process_command == HANDLE_AWTRIX_LOOP_INFO:
                        self.handle_loop_info(awtrix_prefix, payload)
                    elif process_command == HANDLE_AWTRIX_BUTTON_PRESS:
                        self.handle_button_press(awtrix_prefix, payload)

                except queue.Empty:
                    self._check_stats_staleness()
                except Exception as exception_error:
                    self.exception_handler(exception_error, True)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def _get_clock_dev_id_for_prefix(self, awtrix_prefix):
        """Look up the Indigo device ID for a given AWTRIX prefix."""
        return self.globals[AX_PREFIX_TO_DEV_ID].get(awtrix_prefix, None)

    def _format_uptime(self, uptime_seconds):
        """Format uptime seconds into a human-readable string."""
        try:
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            minutes = (uptime_seconds % 3600) // 60
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except (TypeError, ValueError):
            return str(uptime_seconds)

    def _check_stats_staleness(self):
        """Check if any clock devices have stale stats and mark them accordingly."""
        try:
            now = time.time()
            for clock_dev_id, clock_details in self.globals[AX_CLOCKS].items():
                if clock_details.get(AWTRIX_COORDINATOR_DEV_ID) != self.coordinator_dev_id:
                    continue
                last_ts = clock_details.get(LAST_STATS_TIMESTAMP, 0)
                if last_ts == 0:
                    continue  # Never received stats yet
                elapsed = now - last_ts
                if elapsed > STATS_STALE_THRESHOLD:
                    try:
                        clock_dev = indigo.devices[clock_dev_id]
                        current_status = clock_dev.states.get("status", "")
                        if current_status != "offline":
                            key_value_list = [
                                {"key": "status", "value": "offline"},
                                {"key": "onOffState", "value": False},
                                {"key": "brightnessLevel", "value": 0, "uiValue": "offline"},
                            ]
                            clock_dev.updateStatesOnServer(key_value_list)
                            clock_dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOff)
                            self.awtrixLogger.warning(
                                f"No stats received from '{clock_dev.name}' for {int(elapsed)} seconds"
                            )
                    except Exception:
                        pass
        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def handle_button_press(self, awtrix_prefix, payload):
        """Process a button press from the AWTRIX device."""
        try:
            clock_dev_id = self._get_clock_dev_id_for_prefix(awtrix_prefix)
            if clock_dev_id is None:
                return

            # payload contains the button identifier (e.g. "buttonLeft", "buttonMiddle", "buttonRight")
            button_name = payload
            clock_dev = indigo.devices[clock_dev_id]
            clock_dev.updateStateOnServer(key="lastButtonPress", value=button_name)
            self.awtrixLogger.info(f"Button press '{button_name}' on '{clock_dev.name}'")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def handle_stats(self, awtrix_prefix, payload):
        """Process stats JSON from AWTRIX device and update Indigo device states."""
        try:
            clock_dev_id = self._get_clock_dev_id_for_prefix(awtrix_prefix)
            if clock_dev_id is None:
                if self.globals[DEBUG]:
                    self.awtrixLogger.debug(f"No clock device found for AWTRIX prefix: {awtrix_prefix}")
                return

            try:
                stats = json.loads(payload)
            except json.JSONDecodeError as json_error:
                self.awtrixLogger.warning(f"Invalid JSON in stats payload: {json_error}")
                return

            # Record stats timestamp for staleness detection
            self.globals[AX_CLOCKS][clock_dev_id][LAST_STATS_TIMESTAMP] = time.time()

            clock_dev = indigo.devices[clock_dev_id]
            key_value_list = []

            # Add last stats time
            key_value_list.append({"key": "lastStatsTime", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

            # Map AWTRIX stats keys to Indigo states
            for stats_key, state_id in STATS_KEY_MAP.items():
                if stats_key in stats:
                    value = stats[stats_key]
                    ui_value = str(value)

                    if stats_key == "bat":
                        ui_value = f"{value}%"
                    elif stats_key == "bat_raw":
                        ui_value = f"{value} mV"
                    elif stats_key == "temp":
                        ui_value = f"{value} C"
                    elif stats_key == "hum":
                        ui_value = f"{value}%"
                    elif stats_key == "lux":
                        # lux is a boolean indicating if the light sensor is available
                        value = bool(value)
                        ui_value = "Yes" if value else "No"
                    elif stats_key == "wifi_signal":
                        ui_value = f"{value} dBm"
                    elif stats_key == "uptime":
                        ui_value = self._format_uptime(value)

                    if isinstance(value, float):
                        key_value_list.append({"key": state_id, "value": value, "uiValue": ui_value, "decimalPlaces": 1})
                    else:
                        key_value_list.append({"key": state_id, "value": value, "uiValue": ui_value})

            # Handle brightness (bri 0-255 -> Indigo 0-100)
            if "bri" in stats:
                awtrix_bri = stats["bri"]
                indigo_brightness = int((awtrix_bri * 100) / 255)
                key_value_list.append({"key": "brightnessLevel", "value": indigo_brightness, "uiValue": str(indigo_brightness)})

            # Handle matrix on/off state
            if "matrix" in stats:
                matrix_on = stats["matrix"]
                key_value_list.append({"key": "onOffState", "value": matrix_on})

            # Handle indicator states
            for i in range(1, 4):
                indicator_key = f"indicator{i}"
                if indicator_key in stats:
                    indicator_value = stats[indicator_key]
                    # Indicator is active if it has a non-zero/non-empty value
                    is_active = bool(indicator_value) and indicator_value != {"color": [0, 0, 0]}
                    ui_value = "Active" if is_active else "Off"
                    key_value_list.append({"key": f"indicator{i}Active", "value": is_active, "uiValue": ui_value})

            # Update connection status
            key_value_list.append({"key": "status", "value": "connected"})

            # Batch update all states
            if key_value_list:
                clock_dev.updateStatesOnServer(key_value_list)

            # Update state image based on matrix on/off
            if "matrix" in stats:
                if stats["matrix"]:
                    clock_dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOn)
                else:
                    clock_dev.updateStateImageOnServer(indigo.kStateImageSel.DimmerOff)

            if self.globals[DEBUG]:
                self.awtrixLogger.debug(f"Updated stats for '{clock_dev.name}': {len(key_value_list)} states")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def handle_effects_list(self, awtrix_prefix, payload):
        """Cache the list of available effects."""
        try:
            clock_dev_id = self._get_clock_dev_id_for_prefix(awtrix_prefix)
            if clock_dev_id is None:
                return

            try:
                effects = json.loads(payload)
                if clock_dev_id in self.globals[AX_CLOCKS]:
                    self.globals[AX_CLOCKS][clock_dev_id]["cached_effects"] = effects
                    if self.globals[DEBUG]:
                        self.awtrixLogger.debug(f"Cached {len(effects)} effects for device {clock_dev_id}")
            except json.JSONDecodeError:
                pass

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def handle_transitions_list(self, awtrix_prefix, payload):
        """Cache the list of available transitions."""
        try:
            clock_dev_id = self._get_clock_dev_id_for_prefix(awtrix_prefix)
            if clock_dev_id is None:
                return

            try:
                transitions = json.loads(payload)
                if clock_dev_id in self.globals[AX_CLOCKS]:
                    self.globals[AX_CLOCKS][clock_dev_id]["cached_transitions"] = transitions
                    if self.globals[DEBUG]:
                        self.awtrixLogger.debug(f"Cached {len(transitions)} transitions for device {clock_dev_id}")
            except json.JSONDecodeError:
                pass

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def handle_loop_info(self, awtrix_prefix, payload):
        """Cache the current app loop list."""
        try:
            clock_dev_id = self._get_clock_dev_id_for_prefix(awtrix_prefix)
            if clock_dev_id is None:
                return

            try:
                loop_info = json.loads(payload)
                if clock_dev_id in self.globals[AX_CLOCKS]:
                    self.globals[AX_CLOCKS][clock_dev_id]["cached_loop"] = loop_info
                    if self.globals[DEBUG]:
                        self.awtrixLogger.debug(f"Cached app loop for device {clock_dev_id}")
            except json.JSONDecodeError:
                pass

        except Exception as exception_error:
            self.exception_handler(exception_error, True)
