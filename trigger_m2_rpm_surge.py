import paho.mqtt.client as mqtt
import json

client = mqtt.Client("Trigger_M2_RPMSurge")
client.connect("localhost", 1883)

print("Triggering M2 RPM Surge (speed to 1200 RPM)...")
client.publish("factory/triggers/m2_rpm_surge", json.dumps({"trigger": True}))

client.disconnect()
print("Trigger sent.")
