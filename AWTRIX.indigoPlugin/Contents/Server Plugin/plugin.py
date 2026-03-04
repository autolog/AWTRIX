#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# AWTRIX 3 - Plugin © Autolog 2026
#

# ============================== Native Imports ===============================
import base64
from cryptography.fernet import Fernet  # noqa
from cryptography.hazmat.primitives import hashes  # noqa
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # noqa
import json
import logging
import os
import platform
import queue
import sys
import threading
import traceback

# ============================== Custom Imports ===============================
try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

from constants import *
from mqttHandler import ThreadMqttHandler
from awtrixHandler import ThreadAwtrixHandler

import_errors = []
try:
    import paho.mqtt.client as mqtt
except ImportError:
    import_errors.append("paho-mqtt")


# ================================== Header ===================================
__author__    = "Autolog"
__copyright__ = ""
__license__   = "MIT"
__title__     = "AWTRIX 3 Plugin for Indigo"
__version__   = "unused"


def encode(unencrypted_password):
    internal_password = MQTT_ENCRYPTION_PASSWORD_PYTHON_3
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    key = base64.urlsafe_b64encode(kdf.derive(internal_password))
    f = Fernet(key)
    unencrypted_password = unencrypted_password.encode()
    encrypted_password = f.encrypt(unencrypted_password)
    return key, encrypted_password


def decode(key, encrypted_password):
    f = Fernet(key)
    unencrypted_password = f.decrypt(encrypted_password)
    return unencrypted_password


# noinspection PyPep8Naming
class Plugin(indigo.PluginBase):

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super(Plugin, self).__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)

        # Initialise dictionary to store plugin Globals
        self.globals = dict()

        # MASTER DEBUG FLAG FOR DEVELOPMENT ONLY
        self.globals[DEBUG] = False

        self.globals[LOCK_AX_COORDINATOR] = threading.Lock()
        self.globals[LOCK_AX_CLOCKS] = threading.Lock()
        self.globals[QUEUES] = dict()
        self.globals[QUEUES][AWTRIX_QUEUE] = dict()

        # Initialise Indigo plugin info
        self.globals[PLUGIN_INFO] = {}
        self.globals[PLUGIN_INFO][PLUGIN_ID] = plugin_id
        self.globals[PLUGIN_INFO][PLUGIN_DISPLAY_NAME] = plugin_display_name
        self.globals[PLUGIN_INFO][PLUGIN_VERSION] = plugin_version
        self.globals[PLUGIN_INFO][PATH] = indigo.server.getInstallFolderPath()
        self.globals[PLUGIN_INFO][API_VERSION] = indigo.server.apiVersion
        self.globals[PLUGIN_INFO][ADDRESS] = indigo.server.address

        log_format = logging.Formatter("%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.plugin_file_handler.setFormatter(log_format)
        self.plugin_file_handler.setLevel(LOG_LEVEL_INFO)
        self.indigo_log_handler.setLevel(LOG_LEVEL_INFO)

        self.logger = logging.getLogger("Plugin.AWTRIX3")

        # AWTRIX Coordinators - keyed on coordinator Indigo device ID
        self.globals[AX] = dict()

        # AWTRIX Clock devices - keyed on clock Indigo device ID
        self.globals[AX_CLOCKS] = dict()

        # Mapping: AWTRIX prefix -> clock Indigo device ID
        self.globals[AX_PREFIX_TO_DEV_ID] = dict()

        # Set Plugin Config Values
        self.closed_prefs_config_ui(plugin_prefs, False)

    def __del__(self):
        indigo.PluginBase.__del__(self)

    # ========================================================================
    # === Plugin Lifecycle ===================================================
    # ========================================================================

    def startup(self):
        try:
            if len(import_errors):
                self.logger.error(f"AWTRIX 3 Plugin requires the following Python packages: {', '.join(import_errors)}")
                self.logger.error("Install them into the plugin's Packages directory.")
                return

            indigo.devices.subscribeToChanges()

            self.logger.info("AWTRIX 3 Plugin started")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def shutdown(self):
        try:
            self.logger.info("AWTRIX 3 Plugin stopped")
        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    # ========================================================================
    # === Error Handling =====================================================
    # ========================================================================

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method} [{self.globals[PLUGIN_INFO][PLUGIN_VERSION]}]'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.logger.error(log_message)

    # ========================================================================
    # === Plugin Preferences =================================================
    # ========================================================================

    def validate_prefs_config_ui(self, values_dict):
        try:
            errors_dict = indigo.Dict()
            if len(errors_dict) > 0:
                return False, values_dict, errors_dict
            return True, values_dict
        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def closed_prefs_config_ui(self, values_dict, user_cancelled):
        try:
            if user_cancelled:
                return

            # Apply logging levels
            event_log_level = int(values_dict.get("eventLogLevel", LOG_LEVEL_INFO))
            plugin_log_level = int(values_dict.get("pluginLogLevel", LOG_LEVEL_INFO))
            self.indigo_log_handler.setLevel(event_log_level)
            self.plugin_file_handler.setLevel(plugin_log_level)

            self.globals[DEBUG] = values_dict.get("developmentDebug", False)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    # ========================================================================
    # === Plugin Menu ========================================================
    # ========================================================================

    def display_plugin_information(self):
        try:
            def plugin_information_message():
                startup_message_ui = "Plugin Information:\n"
                startup_message_ui += f"{'':={'^'}80}\n"
                startup_message_ui += f"{'Plugin Name:':<30} {self.globals[PLUGIN_INFO][PLUGIN_DISPLAY_NAME]}\n"
                startup_message_ui += f"{'Plugin Version:':<30} {self.globals[PLUGIN_INFO][PLUGIN_VERSION]}\n"
                startup_message_ui += f"{'Plugin ID:':<30} {self.globals[PLUGIN_INFO][PLUGIN_ID]}\n"
                startup_message_ui += f"{'Indigo Version:':<30} {indigo.server.version}\n"
                startup_message_ui += f"{'Indigo License:':<30} {indigo.server.licenseStatus}\n"
                startup_message_ui += f"{'Indigo API Version:':<30} {indigo.server.apiVersion}\n"
                startup_message_ui += f"{'Architecture:':<30} {platform.machine()}\n"
                startup_message_ui += f"{'Python Version:':<30} {sys.version.split(' ')[0]}\n"
                startup_message_ui += f"{'Mac OS Version:':<30} {platform.mac_ver()[0]}\n"
                startup_message_ui += f"{'Plugin Process ID:':<30} {os.getpid()}\n"
                startup_message_ui += f"{'':={'^'}80}\n"
                return startup_message_ui

            self.logger.info(plugin_information_message())

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    # ========================================================================
    # === Device Lifecycle ===================================================
    # ========================================================================

    def device_start_comm(self, dev):
        try:
            dev.stateListOrDisplayStateIdChanged()

            if not dev.enabled:
                return

            if dev.deviceTypeId == "awtrixCoordinator":
                self._start_coordinator(dev)
            elif dev.deviceTypeId == "awtrixClock":
                self._start_clock(dev)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def device_stop_comm(self, dev):
        try:
            if dev.deviceTypeId == "awtrixCoordinator":
                self._stop_coordinator(dev)
            elif dev.deviceTypeId == "awtrixClock":
                self._stop_clock(dev)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def _start_coordinator(self, dev):
        """Start MQTT connection threads for a coordinator device."""
        try:
            dev_id = dev.id

            with self.globals[LOCK_AX_COORDINATOR]:
                if dev_id not in self.globals[AX]:
                    self.globals[AX][dev_id] = dict()

            # Read connection properties from device config
            self.globals[AX][dev_id][MQTT_CLIENT_PREFIX] = dev.pluginProps.get("mqttClientPrefix", "indigo_awtrix")
            self.globals[AX][dev_id][MQTT_CLIENT_ID] = f"{self.globals[AX][dev_id][MQTT_CLIENT_PREFIX]}-D{dev_id}"
            self.globals[AX][dev_id][MQTT_PROTOCOL] = int(dev.pluginProps.get("mqttProtocol", 4))
            self.globals[AX][dev_id][MQTT_IP] = str(dev.pluginProps.get("mqtt_broker_ip", ""))
            self.globals[AX][dev_id][MQTT_PORT] = int(dev.pluginProps.get("mqtt_broker_port", 1883))
            self.globals[AX][dev_id][MQTT_USERNAME] = dev.pluginProps.get("mqtt_username", "")
            self.globals[AX][dev_id][MQTT_PASSWORD] = dev.pluginProps.get("mqtt_password", "")
            self.globals[AX][dev_id][MQTT_ENCRYPTION_KEY] = dev.pluginProps.get("mqtt_password_encryption_key", "").encode('utf-8')
            self.globals[AX][dev_id][MQTT_CONNECTED] = False
            self.globals[AX][dev_id][MQTT_SUBSCRIBED_TOPICS] = set()

            # Collect prefixes from any already-started clock devices linked to this coordinator
            for clock_dev_id, clock_details in self.globals[AX_CLOCKS].items():
                if clock_details.get(AWTRIX_COORDINATOR_DEV_ID) == dev_id:
                    awtrix_prefix = clock_details.get(AWTRIX_PREFIX, "")
                    if awtrix_prefix:
                        self.globals[AX][dev_id][MQTT_SUBSCRIBED_TOPICS].add(awtrix_prefix)

            # Validate required fields
            if not self.globals[AX][dev_id][MQTT_IP]:
                self.logger.warning(f"AWTRIX Coordinator '{dev.name}': MQTT Broker IP not configured")
                dev.updateStateOnServer(key="status", value="not configured")
                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                return

            # Create message queue for this coordinator
            self.globals[QUEUES][AWTRIX_QUEUE][dev_id] = queue.Queue()

            # Start MQTT handler thread
            self.globals[AX][dev_id][MH_EVENT] = threading.Event()
            self.globals[AX][dev_id][MH_THREAD] = ThreadMqttHandler(self.globals, self.globals[AX][dev_id][MH_EVENT], dev_id)
            self.globals[AX][dev_id][MH_THREAD].daemon = True
            self.globals[AX][dev_id][MH_THREAD].start()

            # Start AWTRIX message handler thread
            self.globals[AX][dev_id][AH_EVENT] = threading.Event()
            self.globals[AX][dev_id][AH_THREAD] = ThreadAwtrixHandler(self.globals, self.globals[AX][dev_id][AH_EVENT], dev_id)
            self.globals[AX][dev_id][AH_THREAD].daemon = True
            self.globals[AX][dev_id][AH_THREAD].start()

            self.logger.info(f"AWTRIX Coordinator '{dev.name}' started")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def _stop_coordinator(self, dev):
        """Stop MQTT connection threads for a coordinator device."""
        try:
            dev_id = dev.id

            if dev_id in self.globals[AX]:
                # Signal both threads to stop
                if MH_EVENT in self.globals[AX][dev_id]:
                    self.globals[AX][dev_id][MH_EVENT].set()
                if AH_EVENT in self.globals[AX][dev_id]:
                    self.globals[AX][dev_id][AH_EVENT].set()

                # Wait for threads to finish cleanly
                if MH_THREAD in self.globals[AX][dev_id]:
                    self.globals[AX][dev_id][MH_THREAD].join(10.0)
                if AH_THREAD in self.globals[AX][dev_id]:
                    self.globals[AX][dev_id][AH_THREAD].join(10.0)

            dev.updateStateOnServer(key="status", value="disconnected")
            dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

            self.logger.info(f"AWTRIX Coordinator '{dev.name}' stopped")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def _start_clock(self, dev):
        """Register a clock device and subscribe to its AWTRIX prefix."""
        try:
            dev_id = dev.id
            dev_props = dev.pluginProps

            coordinator_dev_id_str = dev_props.get("awtrix_coordinator_dev_id", "")
            awtrix_prefix = dev_props.get("awtrix_prefix", "").strip()

            if not coordinator_dev_id_str or not awtrix_prefix:
                self.logger.warning(f"AWTRIX Clock '{dev.name}': Coordinator or prefix not configured")
                dev.updateStateOnServer(key="status", value="not configured")
                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                return

            coordinator_dev_id = int(coordinator_dev_id_str)

            with self.globals[LOCK_AX_CLOCKS]:
                self.globals[AX_CLOCKS][dev_id] = {
                    AWTRIX_COORDINATOR_DEV_ID: coordinator_dev_id,
                    AWTRIX_PREFIX: awtrix_prefix,
                }

            # Register prefix mapping
            self.globals[AX_PREFIX_TO_DEV_ID][awtrix_prefix] = dev_id

            # If the coordinator is already running, subscribe to this prefix
            if coordinator_dev_id in self.globals[AX]:
                self.globals[AX][coordinator_dev_id][MQTT_SUBSCRIBED_TOPICS].add(awtrix_prefix)

                # If MQTT is already connected, subscribe dynamically
                if self.globals[AX][coordinator_dev_id].get(MQTT_CONNECTED, False):
                    mqtt_handler = self.globals[AX][coordinator_dev_id].get(MH_THREAD)
                    if mqtt_handler:
                        mqtt_handler.subscribe_prefix(awtrix_prefix)
                    # Initialise stats timestamp so staleness detection will flag offline devices
                    import time
                    self.globals[AX_CLOCKS][dev_id][LAST_STATS_TIMESTAMP] = time.time()
                    key_value_list = [
                        {"key": "status", "value": "connecting ..."},
                        {"key": "brightnessLevel", "value": 0, "uiValue": "connecting ..."},
                    ]
                    dev.updateStatesOnServer(key_value_list)
                    dev.updateStateImageOnServer(indigo.kStateImageSel.TimerOn)
                else:
                    key_value_list = [
                        {"key": "status", "value": "waiting for coordinator"},
                        {"key": "brightnessLevel", "value": 0, "uiValue": "waiting for coordinator"},
                    ]
                    dev.updateStatesOnServer(key_value_list)
                    dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
            else:
                key_value_list = [
                    {"key": "status", "value": "waiting for coordinator"},
                    {"key": "brightnessLevel", "value": 0, "uiValue": "waiting for coordinator"},
                ]
                dev.updateStatesOnServer(key_value_list)
                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

            self.logger.info(f"AWTRIX Clock '{dev.name}' started (prefix: {awtrix_prefix})")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def _stop_clock(self, dev):
        """Unregister a clock device and unsubscribe from its AWTRIX prefix."""
        try:
            dev_id = dev.id

            if dev_id in self.globals[AX_CLOCKS]:
                clock_details = self.globals[AX_CLOCKS][dev_id]
                coordinator_dev_id = clock_details.get(AWTRIX_COORDINATOR_DEV_ID)
                awtrix_prefix = clock_details.get(AWTRIX_PREFIX, "")

                # Unsubscribe from MQTT
                if coordinator_dev_id and coordinator_dev_id in self.globals[AX]:
                    if awtrix_prefix in self.globals[AX][coordinator_dev_id].get(MQTT_SUBSCRIBED_TOPICS, set()):
                        self.globals[AX][coordinator_dev_id][MQTT_SUBSCRIBED_TOPICS].discard(awtrix_prefix)

                    if self.globals[AX][coordinator_dev_id].get(MQTT_CONNECTED, False):
                        mqtt_handler = self.globals[AX][coordinator_dev_id].get(MH_THREAD)
                        if mqtt_handler:
                            mqtt_handler.unsubscribe_prefix(awtrix_prefix)

                # Remove prefix mapping
                if awtrix_prefix in self.globals[AX_PREFIX_TO_DEV_ID]:
                    del self.globals[AX_PREFIX_TO_DEV_ID][awtrix_prefix]

                with self.globals[LOCK_AX_CLOCKS]:
                    del self.globals[AX_CLOCKS][dev_id]

            dev.updateStateOnServer(key="status", value="stopped")
            dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

            self.logger.info(f"AWTRIX Clock '{dev.name}' stopped")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    # ========================================================================
    # === Device Config Validation ===========================================
    # ========================================================================

    def validate_device_config_ui(self, values_dict, type_id, dev_id):
        try:
            errors_dict = indigo.Dict()

            if type_id == "awtrixCoordinator":
                # Validate MQTT broker IP
                mqtt_ip = values_dict.get("mqtt_broker_ip", "").strip()
                if not mqtt_ip:
                    errors_dict["mqtt_broker_ip"] = "MQTT Broker IP is required"

                # Validate MQTT broker port
                try:
                    port = int(values_dict.get("mqtt_broker_port", 1883))
                    if port < 1 or port > 65535:
                        errors_dict["mqtt_broker_port"] = "Port must be between 1 and 65535"
                except ValueError:
                    errors_dict["mqtt_broker_port"] = "Port must be a number"

                # Encrypt password if not already encoded
                if not values_dict.get("mqtt_password_is_encoded", False):
                    password = values_dict.get("mqtt_password", "")
                    if password:
                        key, encrypted_password = encode(password)
                        values_dict["mqtt_password"] = encrypted_password.decode()
                        values_dict["mqtt_password_encryption_key"] = key.decode()
                        values_dict["mqtt_password_is_encoded"] = True

            elif type_id == "awtrixClock":
                # Validate coordinator selection
                coordinator_dev_id = values_dict.get("awtrix_coordinator_dev_id", "")
                if not coordinator_dev_id:
                    errors_dict["awtrix_coordinator_dev_id"] = "Please select an AWTRIX Coordinator"

                # Validate AWTRIX prefix
                awtrix_prefix = values_dict.get("awtrix_prefix", "").strip()
                if not awtrix_prefix:
                    errors_dict["awtrix_prefix"] = "AWTRIX MQTT prefix is required"
                elif " " in awtrix_prefix:
                    errors_dict["awtrix_prefix"] = "AWTRIX prefix cannot contain spaces"

            if len(errors_dict) > 0:
                return False, values_dict, errors_dict

            return True, values_dict

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    # ========================================================================
    # === Dynamic List Methods ===============================================
    # ========================================================================

    def get_coordinator_list(self, filter="", values_dict=None, type_id="", target_id=0):
        """Return list of AWTRIX Coordinator devices for dropdown."""
        try:
            coordinator_list = []
            for dev in indigo.devices.iter("self.awtrixCoordinator"):
                coordinator_list.append((str(dev.id), dev.name))
            if not coordinator_list:
                coordinator_list.append(("", "- No coordinators found -"))
            return coordinator_list
        except Exception as exception_error:
            self.exception_handler(exception_error, True)
            return [("", "- Error -")]

    # ========================================================================
    # === MQTT Publish Helper ================================================
    # ========================================================================

    def publish_mqtt(self, clock_dev_id, topic, payload):
        """Publish an MQTT message via the clock's linked coordinator."""
        try:
            if clock_dev_id not in self.globals[AX_CLOCKS]:
                self.logger.warning(f"Cannot publish: clock device {clock_dev_id} not registered")
                return False

            coordinator_dev_id = self.globals[AX_CLOCKS][clock_dev_id].get(AWTRIX_COORDINATOR_DEV_ID)
            if not coordinator_dev_id or coordinator_dev_id not in self.globals[AX]:
                self.logger.warning(f"Cannot publish: coordinator not found for clock device {clock_dev_id}")
                return False

            if not self.globals[AX][coordinator_dev_id].get(MQTT_CONNECTED, False):
                self.logger.warning(f"Cannot publish: MQTT not connected for coordinator {coordinator_dev_id}")
                return False

            mqtt_client = self.globals[AX][coordinator_dev_id].get(MQTT_CLIENT)
            if mqtt_client:
                mqtt_client.publish(topic, payload)
                return True

            return False

        except Exception as exception_error:
            self.exception_handler(exception_error, True)
            return False

    # ========================================================================
    # === Device Actions (Dimmer) ============================================
    # ========================================================================

    def action_control_device(self, action, dev):
        try:
            if not dev.enabled:
                return

            if dev.deviceTypeId != "awtrixClock":
                return

            dev_id = dev.id
            if dev_id not in self.globals[AX_CLOCKS]:
                return

            awtrix_prefix = self.globals[AX_CLOCKS][dev_id].get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            # ##### TURN ON ######
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                topic = f"{awtrix_prefix}/power"
                payload = json.dumps({"power": True})
                self.publish_mqtt(dev_id, topic, payload)
                self.logger.info(f'sending "turn on" to "{dev.name}"')

            # ##### TURN OFF ######
            elif action.deviceAction == indigo.kDeviceAction.TurnOff:
                topic = f"{awtrix_prefix}/power"
                payload = json.dumps({"power": False})
                self.publish_mqtt(dev_id, topic, payload)
                self.logger.info(f'sending "turn off" to "{dev.name}"')

            # ##### TOGGLE ######
            elif action.deviceAction == indigo.kDeviceAction.Toggle:
                new_state = not dev.onState
                topic = f"{awtrix_prefix}/power"
                payload = json.dumps({"power": new_state})
                self.publish_mqtt(dev_id, topic, payload)
                self.logger.info(f'sending "toggle" to "{dev.name}"')

            # ##### SET BRIGHTNESS ######
            elif action.deviceAction == indigo.kDeviceAction.SetBrightness:
                new_brightness = int(action.actionValue)  # 0-100
                new_bri_255 = int((new_brightness * 255) / 100)
                topic = f"{awtrix_prefix}/settings"
                payload = json.dumps({"BRI": new_bri_255})
                self.publish_mqtt(dev_id, topic, payload)
                self.logger.info(f'sending "set brightness to {new_brightness}%" to "{dev.name}"')

            # ##### BRIGHTEN BY ######
            elif action.deviceAction == indigo.kDeviceAction.BrightenBy:
                new_brightness = min(dev.brightness + int(action.actionValue), 100)
                new_bri_255 = int((new_brightness * 255) / 100)
                topic = f"{awtrix_prefix}/settings"
                payload = json.dumps({"BRI": new_bri_255})
                self.publish_mqtt(dev_id, topic, payload)
                self.logger.info(f'sending "brighten by {int(action.actionValue)}%" to "{dev.name}"')

            # ##### DIM BY ######
            elif action.deviceAction == indigo.kDeviceAction.DimBy:
                new_brightness = max(dev.brightness - int(action.actionValue), 0)
                new_bri_255 = int((new_brightness * 255) / 100)
                topic = f"{awtrix_prefix}/settings"
                payload = json.dumps({"BRI": new_bri_255})
                self.publish_mqtt(dev_id, topic, payload)
                self.logger.info(f'sending "dim by {int(action.actionValue)}%" to "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    # ========================================================================
    # === Custom Actions =====================================================
    # ========================================================================

    def action_send_notification(self, plugin_action, dev):
        """Send a notification to the AWTRIX device."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            payload = {}

            text = self.substitute(plugin_action.props.get("text", ""))
            if text:
                payload["text"] = text

            icon = self.substitute(plugin_action.props.get("icon", ""))
            if icon:
                payload["icon"] = icon

            color = self.substitute(plugin_action.props.get("color", ""))
            if color:
                payload["color"] = color

            try:
                duration = int(self.substitute(plugin_action.props.get("duration", "5")))
                payload["duration"] = duration
            except ValueError:
                payload["duration"] = 5

            sound = self.substitute(plugin_action.props.get("sound", ""))
            if sound:
                payload["sound"] = sound

            if plugin_action.props.get("hold", False):
                payload["hold"] = True

            if plugin_action.props.get("rainbow", False):
                payload["rainbow"] = True

            topic = f"{awtrix_prefix}/notify"
            self.publish_mqtt(dev_id, topic, json.dumps(payload))
            self.logger.info(f'sent notification to "{dev.name}": {text}')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_dismiss_notification(self, plugin_action, dev):
        """Dismiss a held notification."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            topic = f"{awtrix_prefix}/notify/dismiss"
            self.publish_mqtt(dev_id, topic, "")
            self.logger.info(f'dismissed notification on "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_navigate_app(self, plugin_action, dev):
        """Navigate to next or previous app."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            direction = plugin_action.props.get("direction", "next")
            suffix = "nextapp" if direction == "next" else "previousapp"
            topic = f"{awtrix_prefix}/{suffix}"
            self.publish_mqtt(dev_id, topic, "")
            self.logger.info(f'sending "{direction} app" to "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_update_custom_app(self, plugin_action, dev):
        """Create or update a custom app on the AWTRIX device."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            app_name = self.substitute(plugin_action.props.get("appName", "")).strip().replace(" ", "_")
            if not app_name:
                self.logger.warning(f"Update Custom App: app name is required")
                return

            payload = {}

            text = self.substitute(plugin_action.props.get("text", ""))
            if text:
                payload["text"] = text

            icon = self.substitute(plugin_action.props.get("icon", ""))
            if icon:
                payload["icon"] = icon

            color = self.substitute(plugin_action.props.get("color", ""))
            if color:
                payload["color"] = color

            duration = self.substitute(plugin_action.props.get("duration", ""))
            if duration:
                try:
                    payload["duration"] = int(duration)
                except ValueError:
                    pass

            lifetime = self.substitute(plugin_action.props.get("lifetime", "0"))
            try:
                lifetime_int = int(lifetime)
                if lifetime_int > 0:
                    payload["lifetime"] = lifetime_int
            except ValueError:
                pass

            if plugin_action.props.get("rainbow", False):
                payload["rainbow"] = True

            if plugin_action.props.get("noScroll", False):
                payload["noScroll"] = True

            progress = self.substitute(plugin_action.props.get("progress", "-1"))
            try:
                progress_int = int(progress)
                if progress_int >= 0:
                    payload["progress"] = progress_int
                    progress_color = self.substitute(plugin_action.props.get("progressC", ""))
                    if progress_color:
                        payload["progressC"] = progress_color
            except ValueError:
                pass

            topic = f"{awtrix_prefix}/custom/{app_name}"
            self.publish_mqtt(dev_id, topic, json.dumps(payload))
            self.logger.info(f'updated custom app "{app_name}" on "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_remove_custom_app(self, plugin_action, dev):
        """Remove a custom app from the AWTRIX device."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            app_name = plugin_action.props.get("appName", "").strip().replace(" ", "_")
            if not app_name:
                self.logger.warning(f"Remove Custom App: app name is required")
                return

            topic = f"{awtrix_prefix}/custom/{app_name}"
            self.publish_mqtt(dev_id, topic, "")
            self.logger.info(f'removed custom app "{app_name}" from "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_set_indicator(self, plugin_action, dev):
        """Set a colored indicator on the AWTRIX device."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            indicator_num = plugin_action.props.get("indicatorNumber", "1")
            color = self.substitute(plugin_action.props.get("color", "#FF0000"))

            payload = {"color": color}

            blink = self.substitute(plugin_action.props.get("blink", "0"))
            try:
                blink_int = int(blink)
                if blink_int > 0:
                    payload["blink"] = blink_int
            except ValueError:
                pass

            fade = self.substitute(plugin_action.props.get("fade", "0"))
            try:
                fade_int = int(fade)
                if fade_int > 0:
                    payload["fade"] = fade_int
            except ValueError:
                pass

            topic = f"{awtrix_prefix}/indicator{indicator_num}"
            self.publish_mqtt(dev_id, topic, json.dumps(payload))
            self.logger.info(f'set indicator {indicator_num} on "{dev.name}" to {color}')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_clear_indicator(self, plugin_action, dev):
        """Clear a colored indicator on the AWTRIX device."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            indicator_num = plugin_action.props.get("indicatorNumber", "1")
            topic = f"{awtrix_prefix}/indicator{indicator_num}"
            self.publish_mqtt(dev_id, topic, json.dumps({"color": "0"}))
            self.logger.info(f'cleared indicator {indicator_num} on "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_switch_app(self, plugin_action, dev):
        """Switch to a specific app by name."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            app_name = self.substitute(plugin_action.props.get("appName", ""))
            if not app_name:
                self.logger.warning(f"Switch App: app name is required")
                return

            topic = f"{awtrix_prefix}/switch"
            self.publish_mqtt(dev_id, topic, json.dumps({"name": app_name}))
            self.logger.info(f'switching to app "{app_name}" on "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_play_sound(self, plugin_action, dev):
        """Play a sound on the AWTRIX device."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            sound_type = plugin_action.props.get("soundType", "file")
            sound = self.substitute(plugin_action.props.get("sound", ""))
            if not sound:
                self.logger.warning(f"Play Sound: sound value is required")
                return

            if sound_type == "file":
                topic = f"{awtrix_prefix}/sound"
                self.publish_mqtt(dev_id, topic, json.dumps({"sound": sound}))
                self.logger.info(f'playing sound file "{sound}" on "{dev.name}"')
            else:
                topic = f"{awtrix_prefix}/rtttl"
                self.publish_mqtt(dev_id, topic, sound)
                self.logger.info(f'playing RTTTL sound on "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_send_raw_json(self, plugin_action, dev):
        """Send a raw MQTT message to the AWTRIX device."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            topic_suffix = self.substitute(plugin_action.props.get("topicSuffix", "")).strip()
            if not topic_suffix:
                self.logger.warning(f"Send Raw JSON: topic suffix is required")
                return

            payload = self.substitute(plugin_action.props.get("payload", ""))

            # Validate JSON if payload is not empty
            if payload:
                try:
                    json.loads(payload)
                except json.JSONDecodeError as json_error:
                    self.logger.warning(f"Send Raw JSON: invalid JSON payload - {json_error}")
                    return

            topic = f"{awtrix_prefix}/{topic_suffix}"
            self.publish_mqtt(dev_id, topic, payload)
            self.logger.info(f'sent raw MQTT to "{dev.name}": {topic}')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    # ------------------- Phase 3 Actions -------------------

    def action_set_mood_light(self, plugin_action, dev):
        """Set or disable the mood light on the AWTRIX device."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            topic = f"{awtrix_prefix}/moodlight"
            mood_mode = plugin_action.props.get("moodMode", "color")

            if mood_mode == "off":
                self.publish_mqtt(dev_id, topic, "")
                self.logger.info(f'disabled mood light on "{dev.name}"')
                return

            payload = {}

            try:
                brightness = int(self.substitute(plugin_action.props.get("brightness", "170")))
                payload["brightness"] = max(0, min(255, brightness))
            except ValueError:
                payload["brightness"] = 170

            if mood_mode == "kelvin":
                try:
                    kelvin = int(self.substitute(plugin_action.props.get("kelvin", "2300")))
                    payload["kelvin"] = kelvin
                except ValueError:
                    payload["kelvin"] = 2300
            else:
                color = self.substitute(plugin_action.props.get("moodColor", "#FFFFFF"))
                if color:
                    payload["color"] = color

            self.publish_mqtt(dev_id, topic, json.dumps(payload))
            self.logger.info(f'set mood light on "{dev.name}" ({mood_mode})')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_update_settings(self, plugin_action, dev):
        """Update AWTRIX device settings."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            payload = {}

            # Integer settings (text fields)
            for key in ("ATIME", "TSPEED", "SSPEED", "VOL"):
                value = self.substitute(plugin_action.props.get(key, "")).strip()
                if value:
                    try:
                        payload[key] = int(value)
                    except ValueError:
                        self.logger.warning(f'Update Settings: invalid value for {key}: "{value}"')

            # Menu-based integer setting (TEFF)
            teff = plugin_action.props.get("TEFF", "unchanged")
            if teff != "unchanged":
                try:
                    payload["TEFF"] = int(teff)
                except ValueError:
                    pass

            # Boolean settings from menus
            for key in ("ATRANS", "UPPERCASE", "ABRI", "CEL"):
                value = plugin_action.props.get(key, "unchanged")
                if value != "unchanged":
                    payload[key] = value == "true"

            # Color setting (text field)
            tcol = self.substitute(plugin_action.props.get("TCOL", "")).strip()
            if tcol:
                payload["TCOL"] = tcol

            if not payload:
                self.logger.warning(f'Update Settings on "{dev.name}": no settings changed')
                return

            topic = f"{awtrix_prefix}/settings"
            self.publish_mqtt(dev_id, topic, json.dumps(payload))
            self.logger.info(f'updated settings on "{dev.name}": {list(payload.keys())}')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_sleep(self, plugin_action, dev):
        """Put the AWTRIX device to sleep for a specified duration."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            try:
                sleep_seconds = int(self.substitute(plugin_action.props.get("sleepSeconds", "3600")))
                if sleep_seconds <= 0:
                    self.logger.warning(f'Sleep on "{dev.name}": duration must be positive')
                    return
            except ValueError:
                self.logger.warning(f'Sleep on "{dev.name}": invalid duration value')
                return

            topic = f"{awtrix_prefix}/sleep"
            payload = json.dumps({"sleep": sleep_seconds})
            self.publish_mqtt(dev_id, topic, payload)
            self.logger.info(f'sending sleep ({sleep_seconds}s) to "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def action_reboot(self, plugin_action, dev):
        """Reboot the AWTRIX device."""
        try:
            dev_id = dev.id
            awtrix_prefix = self.globals[AX_CLOCKS].get(dev_id, {}).get(AWTRIX_PREFIX, "")
            if not awtrix_prefix:
                return

            topic = f"{awtrix_prefix}/reboot"
            self.publish_mqtt(dev_id, topic, "")
            self.logger.info(f'sending reboot to "{dev.name}"')

        except Exception as exception_error:
            self.exception_handler(exception_error, True)
