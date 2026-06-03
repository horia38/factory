import paho.mqtt.client as mqtt
import json

client = mqtt.Client("Trigger_M4_VibrationJam")
client.connect("localhost", 1883)

print("Triggering M4 Vibration Jam (speed drops to 200 RPM)...")
client.publish("factory/triggers/m4_vibration_jam", json.dumps({"trigger": True}))

client.disconnect()
print("Trigger sent.")
