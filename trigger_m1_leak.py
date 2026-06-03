import paho.mqtt.client as mqtt
import json

client = mqtt.Client("Trigger_M1_Leak")
client.connect("localhost", 1883)

print("Triggering M1 Leak (hopper drops to 15kg)...")
client.publish("factory/triggers/m1_leak", json.dumps({"trigger": True}))

client.disconnect()
print("Trigger sent.")
