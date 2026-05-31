import time
import json
import random
import paho.mqtt.client as mqtt

# --- 1. Machine State ---
machine_state = {
    "machine_id": "M1_Powder_Dispenser",
    "status": "RUNNING",
    "hopper_level_pct": 100.0,
    "dispense_rate_kg_hr": 50.0
}

# --- 2. MQTT Setup ---
# Create a client that will connect to our Docker Mosquitto broker
client = mqtt.Client("Machine1")
client.connect("localhost", 1883)
client.loop_start() # Starts a background thread to handle network traffic

print("Machine 1 (Dispenser) Powered On. Connecting to factory network...")

# --- 3. The Core Simulation Loop ---
try:
    while True:
        # Simulate physics: Hopper level drops as powder is dispensed
        if machine_state["status"] == "RUNNING":
            machine_state["hopper_level_pct"] -= 2.5
            
            # Add some realistic random noise to the dispense rate (between 48 and 52)
            machine_state["dispense_rate_kg_hr"] = round(random.uniform(48.0, 52.0), 1)

        # Exceptional Situation Trigger: If it runs out of powder, stop!
        if machine_state["hopper_level_pct"] <= 0:
            machine_state["hopper_level_pct"] = 0
            machine_state["status"] = "OUT_OF_POWDER"
            print("CRITICAL: Out of powder!")

        # Convert our dictionary to a JSON string
        payload = json.dumps(machine_state)

        # Publish the JSON to the factory network
        client.publish("factory/status/machine1", payload)
        print(f"Published: {payload}")

        # Wait 3 seconds before the next tick
        time.sleep(3)

except KeyboardInterrupt:
    print("\nShutting down Machine 1...")
    client.loop_stop()
    client.disconnect()