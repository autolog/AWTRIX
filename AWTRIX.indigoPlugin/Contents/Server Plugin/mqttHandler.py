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

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    pass

try:
    import paho.mqtt.client as mqtt
except ImportError:
    pass

import logging
import sys
import threading
import time
import traceback

from constants import *


def decode(key, encrypted_password):
    f = Fernet(key)
    unencrypted_password = f.decrypt(encrypted_password)
    return unencrypted_password


# noinspection PyPep8Naming
class ThreadMqttHandler(threading.Thread):

    # This class handles the MQTT broker connection for an AWTRIX Coordinator

    def __init__(self, pluginGlobals, event, coordinator_dev_id):
        try:
            threading.Thread.__init__(self)

            self.globals = pluginGlobals

            self.mqtt_client = None

            self.coordinator_dev_id = coordinator_dev_id

            self.mqttHandlerLogger = logging.getLogger("Plugin.MQTT")

            self.threadStop = event

            self.bad_disconnection = False

            self.mqtt_message_sequence = 0

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
        self.mqttHandlerLogger.error(log_message)

    def run(self):
        try:
            coordinator_dev = indigo.devices[self.coordinator_dev_id]
            coordinator_dev.updateStateOnServer(key="status", value="disconnected")
            coordinator_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

            if self.globals[DEBUG]:
                self.mqttHandlerLogger.info(f"Client ID: {self.globals[AX][self.coordinator_dev_id][MQTT_CLIENT_ID]}")

            self.mqtt_client = mqtt.Client(
                client_id=self.globals[AX][self.coordinator_dev_id][MQTT_CLIENT_ID],
                clean_session=True,
                userdata=None,
                protocol=self.globals[AX][self.coordinator_dev_id][MQTT_PROTOCOL]
            )

            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_disconnect = self.on_disconnect
            self.mqtt_client.on_subscribe = self.on_subscribe

            # Subscribe to each clock's prefix
            for awtrix_prefix in self.globals[AX][self.coordinator_dev_id][MQTT_SUBSCRIBED_TOPICS]:
                mqtt_subscription = f"{awtrix_prefix}/#"
                self.mqtt_client.message_callback_add(mqtt_subscription, self.handle_message)

            mqtt_connected = False
            try:
                broker_name = coordinator_dev.name
                decoded_password = ""
                if self.globals[AX][self.coordinator_dev_id][MQTT_PASSWORD] != "":
                    encrypted_password = self.globals[AX][self.coordinator_dev_id][MQTT_PASSWORD].encode()
                    decoded_password = decode(
                        self.globals[AX][self.coordinator_dev_id][MQTT_ENCRYPTION_KEY],
                        encrypted_password
                    )

                if decoded_password != "" or self.globals[AX][self.coordinator_dev_id][MQTT_USERNAME] != "":
                    self.mqtt_client.username_pw_set(
                        username=self.globals[AX][self.coordinator_dev_id][MQTT_USERNAME],
                        password=decoded_password
                    )

                self.mqtt_client.connect(
                    host=self.globals[AX][self.coordinator_dev_id][MQTT_IP],
                    port=self.globals[AX][self.coordinator_dev_id][MQTT_PORT],
                    keepalive=60,
                    bind_address=""
                )
                mqtt_connected = True
            except Exception as exception_error:
                self.mqttHandlerLogger.error(
                    f"Plugin is unable to connect to the MQTT Broker at "
                    f"{self.globals[AX][self.coordinator_dev_id][MQTT_IP]}:"
                    f"{self.globals[AX][self.coordinator_dev_id][MQTT_PORT]}. "
                    f"Is it running? Connection error reported as '{exception_error}'"
                )
                self.exception_handler(exception_error, True)

            if mqtt_connected:
                self.globals[AX][self.coordinator_dev_id][MQTT_CLIENT] = self.mqtt_client
                self.mqtt_client.loop_start()

                while not self.threadStop.is_set():
                    try:
                        time.sleep(2)
                    except Exception:
                        pass

            self.handle_quit()

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def on_connect(self, client, userdata, flags, rc):  # noqa [Unused parameter values]
        try:
            # Subscribe to all registered AWTRIX prefixes
            for awtrix_prefix in self.globals[AX][self.coordinator_dev_id][MQTT_SUBSCRIBED_TOPICS]:
                subscription_topic = f"{awtrix_prefix}/#"
                if self.globals[DEBUG]:
                    self.mqttHandlerLogger.info(f"AWTRIX: Subscribing to {subscription_topic}")
                self.mqtt_client.subscribe(subscription_topic, qos=1)

            self.globals[AX][self.coordinator_dev_id][MQTT_CONNECTED] = True
            coordinator_dev = indigo.devices[self.coordinator_dev_id]
            coordinator_dev.updateStateOnServer(key="status", value="connected")
            coordinator_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            # Initialise stats timestamps for linked clocks so staleness detection works
            now = time.time()
            for clock_dev_id, clock_details in self.globals[AX_CLOCKS].items():
                if clock_details.get(AWTRIX_COORDINATOR_DEV_ID) == self.coordinator_dev_id:
                    if clock_details.get(LAST_STATS_TIMESTAMP, 0) == 0:
                        clock_details[LAST_STATS_TIMESTAMP] = now
                    try:
                        clock_dev = indigo.devices[clock_dev_id]
                        if clock_dev.states.get("status", "") == "waiting for coordinator":
                            key_value_list = [
                                {"key": "status", "value": "connecting ..."},
                                {"key": "brightnessLevel", "value": 0, "uiValue": "connecting ..."},
                            ]
                            clock_dev.updateStatesOnServer(key_value_list)
                            clock_dev.updateStateImageOnServer(indigo.kStateImageSel.TimerOn)
                    except Exception:
                        pass

            if self.bad_disconnection:
                self.bad_disconnection = False
                connection_ui = "Reconnected"
            else:
                connection_ui = "Connected"
            self.mqttHandlerLogger.info(
                f"{connection_ui} to MQTT Broker at "
                f"{self.globals[AX][self.coordinator_dev_id][MQTT_IP]}:"
                f"{self.globals[AX][self.coordinator_dev_id][MQTT_PORT]}"
            )

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def on_disconnect(self, client, userdata, rc):  # noqa [Unused parameter values]
        try:
            self.globals[AX][self.coordinator_dev_id][MQTT_CONNECTED] = False
            if rc != 0:
                self.mqttHandlerLogger.warning(
                    f"Plugin encountered an unexpected disconnection from MQTT Broker at "
                    f"{self.globals[AX][self.coordinator_dev_id][MQTT_IP]}:"
                    f"{self.globals[AX][self.coordinator_dev_id][MQTT_PORT]}. "
                    f"[Code {rc}]. Retrying connection ..."
                )
                self.bad_disconnection = True
            else:
                self.mqttHandlerLogger.info(
                    f"Disconnected from MQTT Broker at "
                    f"{self.globals[AX][self.coordinator_dev_id][MQTT_IP]}:"
                    f"{self.globals[AX][self.coordinator_dev_id][MQTT_PORT]}"
                )
                self.mqtt_client.loop_stop()

            coordinator_dev = indigo.devices[self.coordinator_dev_id]
            coordinator_dev.updateStateOnServer(key="status", value="disconnected")
            coordinator_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

            # Update all linked clock devices to disconnected
            for clock_dev_id, clock_details in self.globals[AX_CLOCKS].items():
                if clock_details.get(AWTRIX_COORDINATOR_DEV_ID) == self.coordinator_dev_id:
                    try:
                        clock_dev = indigo.devices[clock_dev_id]
                        clock_dev.updateStateOnServer(key="status", value="disconnected")
                        clock_dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                    except Exception:
                        pass

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def handle_quit(self):
        try:
            if self.mqtt_client:
                self.mqtt_client.disconnect()
                self.mqtt_client.loop_stop()
        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def on_subscribe(self, client, userdata, mid, granted_qos):  # noqa [Unused parameter values]
        try:
            pass
        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def handle_message(self, client, userdata, msg):  # noqa [Unused parameter values: client, userdata]
        try:
            self.mqtt_message_sequence += 1
            topic = msg.topic
            topic_list = topic.split("/")
            payload = msg.payload.decode('utf-8')

            if len(topic_list) < 2:
                return

            # topic_list[0] is the AWTRIX prefix
            awtrix_prefix = topic_list[0]

            # Determine message type from topic structure
            if len(topic_list) == 2 and topic_list[1] == "stats":
                process_command = HANDLE_AWTRIX_STATS
            elif len(topic_list) == 3 and topic_list[1] == "stats" and topic_list[2] == "effects":
                process_command = HANDLE_AWTRIX_EFFECTS_LIST
            elif len(topic_list) == 3 and topic_list[1] == "stats" and topic_list[2] == "transitions":
                process_command = HANDLE_AWTRIX_TRANSITIONS_LIST
            elif len(topic_list) == 3 and topic_list[1] == "stats" and topic_list[2] == "loop":
                process_command = HANDLE_AWTRIX_LOOP_INFO
            elif len(topic_list) == 3 and topic_list[1] == "stats" and topic_list[2].startswith("button"):
                process_command = HANDLE_AWTRIX_BUTTON_PRESS
                payload = topic_list[2]  # e.g. "buttonLeft", "buttonMiddle", "buttonRight"
            else:
                # Other topics (screen data, etc.) - skip for now
                if self.globals[DEBUG]:
                    self.mqttHandlerLogger.debug(f"AWTRIX unhandled topic: {topic}")
                return

            self.globals[QUEUES][AWTRIX_QUEUE][self.coordinator_dev_id].put(
                [self.mqtt_message_sequence, process_command, self.coordinator_dev_id, awtrix_prefix, topic, payload]
            )

        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def subscribe_prefix(self, awtrix_prefix):
        """Subscribe to a new AWTRIX prefix (called when a clock device starts)."""
        try:
            if self.mqtt_client and self.globals[AX][self.coordinator_dev_id].get(MQTT_CONNECTED, False):
                subscription_topic = f"{awtrix_prefix}/#"
                self.mqtt_client.message_callback_add(subscription_topic, self.handle_message)
                self.mqtt_client.subscribe(subscription_topic, qos=1)
                self.mqttHandlerLogger.info(f"Subscribed to AWTRIX prefix: {awtrix_prefix}")
        except Exception as exception_error:
            self.exception_handler(exception_error, True)

    def unsubscribe_prefix(self, awtrix_prefix):
        """Unsubscribe from an AWTRIX prefix (called when a clock device stops)."""
        try:
            if self.mqtt_client and self.globals[AX][self.coordinator_dev_id].get(MQTT_CONNECTED, False):
                subscription_topic = f"{awtrix_prefix}/#"
                self.mqtt_client.unsubscribe(subscription_topic)
                self.mqtt_client.message_callback_remove(subscription_topic)
                self.mqttHandlerLogger.info(f"Unsubscribed from AWTRIX prefix: {awtrix_prefix}")
        except Exception as exception_error:
            self.exception_handler(exception_error, True)
