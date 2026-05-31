import time
import json
import random
import paho.mqtt.client as mqtt

# Machine state includes output buffer for granulator
machine_state = {
    "machine_id": "M1_Powder_Dispenser",
    "status": "IDLE",  # IDLE, DISPENSING, LOW_POWDER, REFILLING
    "hopper_level_kg": 100.0,  # Raw powder hopper
    "hopper_capacity_kg": 100.0,
    "output_buffer_kg": 0.0,  # Buffer for machine2 to consume
    "output_buffer_capacity_kg": 25.0,
    "dispense_rate_kg_per_cycle": 5.0,
    "cycles_completed": 0,
    "total_powder_dispensed_kg": 0.0
}

active_batch_id = None
batch_count = 0

def on_message(client, userdata, msg):
    """Handle commands from master agent."""
    global active_batch_id, batch_count
    
    try:
        print(f"[DEBUG M1] Received message on topic: {msg.topic}")
        command = json.loads(msg.payload.decode('utf-8'))
        print(f"[DEBUG M1] Parsed command: {command}")
        action = command.get("action")
        print(f"[DEBUG M1] Action: {action}")
        
        if action == "start_batch":
            active_batch_id = command.get("batch_id")
            batch_count += 1
            machine_state["status"] = "DISPENSING"
            print(f"\n✓ [M1 COMMAND] Starting batch {active_batch_id}, status now: {machine_state['status']}")
            
        elif action == "pause":
            machine_state["status"] = "IDLE"
            print(f"\n[M1 COMMAND] Paused")
            
        elif action == "refill":
            machine_state["hopper_level_kg"] = machine_state["hopper_capacity_kg"]
            machine_state["status"] = "IDLE"
            print(f"\n[M1 COMMAND] Refilled hopper to {machine_state['hopper_level_kg']} kg")
            
    except json.JSONDecodeError as e:
        print(f"[ERROR M1] JSON decode failed: {e}")
    except Exception as e:
        print(f"[ERROR M1] Unexpected error in on_message: {e}")

client = mqtt.Client("Machine1_Dispenser")
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("factory/commands/machine1")
client.loop_start()

print("Machine 1 (Powder Dispenser) Powered On...")

try:
    cycle = 0
    while True:
        # Dispense powder into output buffer if active and hopper has powder
        if cycle % 20 == 0:  # Debug print every 60 seconds
            print(f"[DEBUG M1] Status={machine_state['status']}, active_batch_id={active_batch_id}, hopper={machine_state['hopper_level_kg']:.1f}kg, buffer={machine_state['output_buffer_kg']:.1f}kg")
        
        if machine_state["status"] == "DISPENSING" and active_batch_id:
            if machine_state["hopper_level_kg"] > 0 and machine_state["output_buffer_kg"] < machine_state["output_buffer_capacity_kg"]:
                dispense_amount = min(
                    machine_state["dispense_rate_kg_per_cycle"],
                    machine_state["hopper_level_kg"],
                    machine_state["output_buffer_capacity_kg"] - machine_state["output_buffer_kg"]
                )
                machine_state["hopper_level_kg"] -= dispense_amount
                machine_state["output_buffer_kg"] += dispense_amount
                machine_state["total_powder_dispensed_kg"] += dispense_amount
                machine_state["cycles_completed"] += 1
                
                # Signal to machine2 that powder is available
                client.publish("factory/events/machine1_powder_ready", 
                             json.dumps({"batch_id": active_batch_id, "amount_kg": machine_state["output_buffer_kg"]}))
            
            elif machine_state["hopper_level_kg"] <= 0:
                machine_state["status"] = "LOW_POWDER"
                client.publish("factory/alerts/machine1_low_powder", 
                             json.dumps({"batch_id": active_batch_id, "hopper_level_kg": 0}))
                print("ALERT: Low on powder!")
        
        # Publish status periodically
        cycle += 1
        if cycle % 2 == 0:  # Every 6 seconds (3s * 2)
            client.publish("factory/status/machine1", json.dumps(machine_state))

        time.sleep(3)

except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()