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
    "dispense_rate_kg_per_cycle": 1.0,
    "cycles_completed": 0,
    "total_powder_dispensed_kg": 0.0
}

active_batch_id = None
batch_count = 0

def on_message(client, userdata, msg):
    """Handle commands from master agent."""
    global active_batch_id, batch_count
    
    try:
        if "triggers/m1_leak" in msg.topic:
            machine_state["hopper_level_kg"] = 15.0
            machine_state["leak_triggered"] = True
            print(f"\n[M1 TRIGGER] Leak triggered! Hopper level dropped to 15.0 kg")
            return
            
        command = json.loads(msg.payload.decode('utf-8'))
        action = command.get("action")
        
        if action == "start_batch":
            active_batch_id = command.get("batch_id")
            batch_count += 1
            machine_state["status"] = "DISPENSING"
            machine_state["batch_dispensed_kg"] = 0.0
            print(f"\n✓ [M1 COMMAND] Starting batch {active_batch_id}, status now: {machine_state['status']}")
            
        elif action == "pause":
            machine_state["status"] = "IDLE"
            print(f"\n[M1 COMMAND] Paused")
            
        elif action == "refill":
            machine_state["hopper_level_kg"] = machine_state["hopper_capacity_kg"]
            machine_state["status"] = "IDLE"
            print(f"\n[M1 COMMAND] Refilled hopper to {machine_state['hopper_level_kg']} kg")
    except Exception as e:
        print(f"[ERROR M1] Unexpected error in on_message: {e}")

    try:
        if "batch_completed" in msg.topic:
            # Batch finished, reset for next one
            print(f"\n[M1 RESET] Batch complete, resetting for next batch")
            active_batch_id = None
            machine_state["status"] = "IDLE"
            machine_state["cycles_completed"] = 0
            
    except Exception as e:
        print(f"[ERROR M1] Batch completion handling: {e}")
            
    except json.JSONDecodeError as e:
        print(f"[ERROR M1] JSON decode failed: {e}")
    except Exception as e:
        print(f"[ERROR M1] Unexpected error in on_message: {e}")

client = mqtt.Client("Machine1_Dispenser")
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("factory/commands/machine1")
client.subscribe("factory/events/batch_completed")  # Listen for batch completion to reset
client.subscribe("factory/triggers/m1_leak")
client.loop_start()

print("Machine 1 (Powder Dispenser) Powered On...")

try:
    cycle = 0
    while True:
        # Dispense powder into output buffer if active and hopper has powder
        if cycle % 20 == 0:  # Debug print every 60 seconds
            print(f"[DEBUG M1] Status={machine_state['status']}, active_batch_id={active_batch_id}, hopper={machine_state['hopper_level_kg']:.1f}kg, buffer={machine_state['output_buffer_kg']:.1f}kg")
        
        if machine_state["status"] == "DISPENSING" and active_batch_id:
            # Stop dispensing if we reached batch limit (20kg) to allow the batch to finish
            if machine_state.get("batch_dispensed_kg", 0.0) >= 20.0:
                pass # Wait for pipeline to finish and new batch to start
            elif machine_state["hopper_level_kg"] > 0 and machine_state["output_buffer_kg"] < machine_state["output_buffer_capacity_kg"]:
                base_dispense = min(
                    machine_state["dispense_rate_kg_per_cycle"],
                    machine_state["hopper_level_kg"],
                    machine_state["output_buffer_capacity_kg"] - machine_state["output_buffer_kg"]
                )
                
                # PHYSICS: Feed Starvation Cascade
                if machine_state["hopper_level_kg"] < 20.0:
                    starvation_factor = random.uniform(0.5, 0.7)
                    dispense_amount = base_dispense * starvation_factor
                    print(f"[PHYSICS M1] Hopper low (<20kg). Starvation factor {starvation_factor:.2f} applied. Dispensing {dispense_amount:.2f} kg instead of {base_dispense:.2f} kg.")
                else:
                    dispense_amount = base_dispense
                    
                if machine_state.get("leak_triggered", False):
                    machine_state["hopper_level_kg"] -= dispense_amount
                    
                machine_state["batch_dispensed_kg"] = machine_state.get("batch_dispensed_kg", 0.0) + dispense_amount
                machine_state["output_buffer_kg"] += dispense_amount
                machine_state["total_powder_dispensed_kg"] += dispense_amount
                machine_state["cycles_completed"] += 1
                
                # Signal to machine2 that powder is available, then CLEAR buffer (handed off)
                amount_to_send = machine_state["output_buffer_kg"]
                client.publish("factory/events/machine1_powder_ready", 
                             json.dumps({"batch_id": active_batch_id, "amount_kg": amount_to_send}))
                machine_state["output_buffer_kg"] = 0  # Clear after publishing (handed off)
            
            elif machine_state["hopper_level_kg"] <= 0:
                machine_state["status"] = "LOW_POWDER"
                client.publish("factory/alerts/machine1_low_powder", 
                             json.dumps({"batch_id": active_batch_id, "hopper_level_kg": 0}))
                print("ALERT: Low on powder!")
        
        # Publish status periodically
        cycle += 1
        if True:
            client.publish("factory/status/machine1", json.dumps(machine_state))

        time.sleep(3)

except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()