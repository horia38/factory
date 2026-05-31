#!/usr/bin/env python3
"""Quick MQTT diagnostic script"""

import paho.mqtt.client as mqtt
import json
import time

print("="*60)
print("🔍 MQTT CONNECTIVITY TEST")
print("="*60)

# Test 1: Can we connect to broker?
print("\n[TEST 1] Connecting to MQTT broker...")
client = mqtt.Client("MQTTTest")
try:
    client.connect("localhost", 1883)
    print("✓ Connected to broker successfully!")
except Exception as e:
    print(f"✗ FAILED to connect: {e}")
    print("  Make sure mosquitto is running: mosquitto")
    exit(1)

# Test 2: Can we publish a message?
print("\n[TEST 2] Publishing test message...")
client.loop_start()
time.sleep(0.5)

test_payload = {"action": "start_batch", "batch_id": "TEST_001"}
result = client.publish("factory/commands/test", json.dumps(test_payload))
if result.rc == 0:
    print(f"✓ Published successfully: {test_payload}")
else:
    print(f"✗ Publish failed with code: {result.rc}")

# Test 3: Can we receive the message back?
print("\n[TEST 3] Subscribing to test topic...")

received_messages = []

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode('utf-8'))
    received_messages.append(payload)
    print(f"✓ Received message: {payload}")

client.on_message = on_message
client.subscribe("factory/commands/test")
time.sleep(1)

if received_messages:
    print("✓ MQTT is working correctly!")
else:
    print("⚠️  No message received (might be timing issue)")

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)

client.loop_stop()
client.disconnect()
