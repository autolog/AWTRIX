#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# AWTRIX 3 - Plugin © Autolog 2026
#

import logging

# ============================== Custom Imports ===============================
try:
    import indigo  # noqa
except ImportError:
    pass

number = -1

debug_show_constants = False
debug_use_labels = True


def constant_id(constant_label):  # Auto increment constant id

    global number
    if debug_show_constants and number == -1:
        indigo.server.log("AWTRIX 3 Plugin internal Constant Name mapping ...", level=logging.DEBUG)
    number += 1
    if debug_show_constants:
        indigo.server.log(f"{number}: {constant_label}", level=logging.DEBUG)
    if debug_use_labels:
        return constant_label
    else:
        return number


# Encryption
MQTT_ENCRYPTION_PASSWORD_PYTHON_3 = b"indigo_to_awtrix3"

# Plugin info
PLUGIN_INFO = constant_id("PLUGIN_INFO")
PLUGIN_ID = constant_id("PLUGIN_ID")
PLUGIN_DISPLAY_NAME = constant_id("PLUGIN_DISPLAY_NAME")
PLUGIN_VERSION = constant_id("PLUGIN_VERSION")
PATH = constant_id("PATH")
API_VERSION = constant_id("API_VERSION")
ADDRESS = constant_id("ADDRESS")
DEBUG = constant_id("DEBUG")

# Logging levels
LOG_LEVEL_NOT_SET = 0
LOG_LEVEL_DEBUGGING = 10
LOG_LEVEL_TOPIC = 15
LOG_LEVEL_INFO = 20
LOG_LEVEL_WARNING = 30
LOG_LEVEL_ERROR = 40
LOG_LEVEL_CRITICAL = 50

# Locks
LOCK_AX_COORDINATOR = constant_id("LOCK_AX_COORDINATOR")
LOCK_AX_CLOCKS = constant_id("LOCK_AX_CLOCKS")

# Queues
QUEUES = constant_id("QUEUES")
AWTRIX_QUEUE = constant_id("AWTRIX_QUEUE")

# AWTRIX Coordinator dict - keyed on coordinator Indigo device ID
AX = constant_id("AX [AWTRIX COORDINATORS]")

# AWTRIX Clock devices dict - keyed on clock Indigo device ID
AX_CLOCKS = constant_id("AX_CLOCKS")

# Mapping: AWTRIX prefix -> clock Indigo device ID
AX_PREFIX_TO_DEV_ID = constant_id("AX_PREFIX_TO_DEV_ID")

# MQTT connection constants
MQTT_CLIENT = constant_id("MQTT_CLIENT")
MQTT_CLIENT_ID = constant_id("MQTT_CLIENT_ID")
MQTT_CLIENT_PREFIX = constant_id("MQTT_CLIENT_PREFIX")
MQTT_CONNECTED = constant_id("MQTT_CONNECTED")
MQTT_CONNECTION_INITIALISED = constant_id("MQTT_CONNECTION_INITIALISED")
MQTT_ENCRYPTION_KEY = constant_id("MQTT_ENCRYPTION_KEY")
MQTT_IP = constant_id("MQTT_IP")
MQTT_PASSWORD = constant_id("MQTT_PASSWORD")
MQTT_PORT = constant_id("MQTT_PORT")
MQTT_PROTOCOL = constant_id("MQTT_PROTOCOL")
MQTT_USERNAME = constant_id("MQTT_USERNAME")
MQTT_SUBSCRIBED_TOPICS = constant_id("MQTT_SUBSCRIBED_TOPICS")

# AWTRIX clock device constants
AWTRIX_PREFIX = constant_id("AWTRIX_PREFIX")
AWTRIX_COORDINATOR_DEV_ID = constant_id("AWTRIX_COORDINATOR_DEV_ID")
LAST_STATS_TIMESTAMP = constant_id("LAST_STATS_TIMESTAMP")

# Stats staleness threshold (seconds)
STATS_STALE_THRESHOLD = 60

# Thread event and thread references
MH_EVENT = constant_id("MH_EVENT")  # MQTT Handler thread event
MH_THREAD = constant_id("MH_THREAD")  # MQTT Handler thread
AH_EVENT = constant_id("AH_EVENT")  # AWTRIX Handler thread event
AH_THREAD = constant_id("AH_THREAD")  # AWTRIX Handler thread

# Message type constants (for queue routing)
HANDLE_AWTRIX_STATS = constant_id("HANDLE_AWTRIX_STATS")
HANDLE_AWTRIX_EFFECTS_LIST = constant_id("HANDLE_AWTRIX_EFFECTS_LIST")
HANDLE_AWTRIX_TRANSITIONS_LIST = constant_id("HANDLE_AWTRIX_TRANSITIONS_LIST")
HANDLE_AWTRIX_LOOP_INFO = constant_id("HANDLE_AWTRIX_LOOP_INFO")
HANDLE_AWTRIX_BUTTON_PRESS = constant_id("HANDLE_AWTRIX_BUTTON_PRESS")

# Stats JSON key mappings to Indigo state IDs
STATS_KEY_MAP = {
    "bat": "battery",
    "bat_raw": "batteryRaw",
    "temp": "temperature",
    "hum": "humidity",
    "lux": "luxSensorEnabled",
    "ldr_raw": "ldrRaw",
    "wifi_signal": "wifiSignal",
    "ram": "freeRam",
    "uptime": "uptime",
    "version": "firmwareVersion",
    "uid": "uid",
    "app": "currentApp",
    "messages": "messageCount",
}
