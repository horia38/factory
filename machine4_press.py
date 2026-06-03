import time
import json
import random
import paho.mqtt.client as mqtt

machine_state = {
    "machine_id": "M4_Pill_Press",
    "status": "IDLE",  # IDLE, PRESSING, WAITING_INPUT
    "input_buffer_kg": 0.0,  # Receives dried granules from machine3
    "input_buffer_capacity_kg": 15.0,
    "output_buffer_pills": 0,  # Number of pills produced
    "output_buffer_capacity_pills": 1000,
    "input_moisture_pct": 2.0,  # Tracked from machine3
    "speed_rpm": 1000,
    "vibration_hz": 75.0,
    "pressure_bar": 250.0,
    "defect_rate_pct": 0.5,  # Affected by moisture and speed
    "pills_produced": 0,
    "cycles_completed": 0
}

active_batch_id = None
incoming_moisture = 2.0
jam_active = False
jam_timer = 0

def on_message(client, userdata, msg):
    """Handle commands and events."""
    global active_batch_id, incoming_moisture, jam_active, jam_timer
    
    try:
        topic = msg.topic
        
        if "triggers/m4_vibration_jam" in topic:
            jam_active = True
            jam_timer = 30  # Lasts 30 seconds
            machine_state["speed_rpm"] = 200
            print(f"\n[M4 TRIGGER] Vibration Jam triggered! Speed forced down to 200 RPM for 30s")
            return
            
        payload = json.loads(msg.payload.decode('utf-8'))
        
        if "commands/machine4" in topic:
            action = payload.get("action")
            
            if action == "start_batch":
                active_batch_id = payload.get("batch_id")
                machine_state["status"] = "PRESSING"
                machine_state["target_rpm"] = payload.get("speed_rpm", 1000)
                machine_state["speed_rpm"] = machine_state["target_rpm"]
                print(f"\n✓ [M4 COMMAND] Starting batch {active_batch_id}, speed: {machine_state['speed_rpm']} RPM, status now: {machine_state['status']}")
                
            elif action == "set_rpm":
                machine_state["target_rpm"] = payload.get("value", 1000)
                print(f"\n[M4 COMMAND] Adjusting target speed to {machine_state['target_rpm']} RPM")
                
            elif action == "pause":
                machine_state["status"] = "IDLE"
                print(f"\n[M4 COMMAND] Paused")
                
        elif "machine3_granules_dried" in topic:
            # Machine3 signals dried granules are ready
            amount = payload.get("amount_kg", 0)
            moisture = payload.get("moisture_pct", 2.0)
            incoming_moisture = moisture
            
            if amount > 0:
                transfer = min(amount, machine_state["input_buffer_capacity_kg"] - machine_state["input_buffer_kg"])
                if transfer > 0:
                    machine_state["input_buffer_kg"] += transfer
                    machine_state["input_moisture_pct"] = moisture
                    
                    if machine_state["status"] == "WAITING_INPUT":
                        machine_state["status"] = "PRESSING"
                        
                    # Confirm consumption back to M3
                    client.publish("factory/events/machine4_consumed", json.dumps({"consumed_kg": transfer}))
                    
                    # Resume processing if we were waiting for input
                    if machine_state["status"] == "WAITING_INPUT" and active_batch_id:
                        machine_state["status"] = "PRESSING"
                        print(f"[RESUME] Resuming PRESSING, got {transfer} kg granules. Moisture: {moisture:.1f}%")
                    else:
                        print(f"[INPUT] Received {transfer} kg granules. Moisture: {moisture:.1f}%")
                
    except json.JSONDecodeError as e:
        print(f"[ERROR M4] JSON decode failed: {e}")
    except Exception as e:
        print(f"[ERROR M4] Unexpected error in on_message: {e}")

client = mqtt.Client("Machine4_Press")
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("factory/commands/machine4")
client.subscribe("factory/events/machine3_granules_dried")
client.subscribe("factory/triggers/m4_vibration_jam")
client.loop_start()

print("Machine 4 (Pill Press) Powered On...")

try:
    cycle = 0
    while True:
        # Calculate vibration based on speed
        if cycle % 20 == 0:  # Debug print every 60 seconds
            print(f"[DEBUG M4] Status={machine_state['status']}, active_batch_id={active_batch_id}, RPM={machine_state['speed_rpm']}, input={machine_state['input_buffer_kg']:.1f}kg, output={machine_state['output_buffer_pills']} pills")
        if "target_rpm" not in machine_state:
            machine_state["target_rpm"] = 1000
            
        if jam_active:
            jam_timer -= 3
            if jam_timer <= 0:
                jam_active = False
                print(f"[M4] Jam cleared, speeding back up.")
            else:
                machine_state["speed_rpm"] = 200
        else:
            # Gradually stabilize to target
            if machine_state["speed_rpm"] < machine_state["target_rpm"]:
                machine_state["speed_rpm"] = min(machine_state["target_rpm"], machine_state["speed_rpm"] + 50)
            elif machine_state["speed_rpm"] > machine_state["target_rpm"]:
                machine_state["speed_rpm"] = max(machine_state["target_rpm"], machine_state["speed_rpm"] - 50)

        base_vib = (machine_state["speed_rpm"] / 1000) * 75.0
        machine_state["vibration_hz"] = round(base_vib + random.uniform(-3.0, 3.0), 1)
        
        # Press pills if we have input
        if machine_state["status"] == "PRESSING" and active_batch_id:
            if machine_state["input_buffer_kg"] > 0 and machine_state["output_buffer_pills"] < machine_state["output_buffer_capacity_pills"]:
                # Each kg of granules makes ~200 pills
                pills_per_kg = 200
                
                # PHYSICS: Process amount is dependent on speed_rpm (1000 RPM -> 1.0 kg)
                max_process = 1.0 * (machine_state["speed_rpm"] / 1000.0)
                process_amount = min(max_process, machine_state["input_buffer_kg"])
                pills_made = int(process_amount * pills_per_kg)
                
                # CRITICAL PHYSICS: Moisture and vibration affect defect rate
                # Too dry (low moisture) + high vibration = crumbly pills
                # Formula: base defect + (dryness penalty) + (vibration penalty)
                base_defect = 0.3
                dryness_penalty = 0 if machine_state["input_moisture_pct"] >= 1.5 else (1.5 - machine_state["input_moisture_pct"]) * 3.0
                
                # PHYSICS: Thermal Cascade Defect Spike
                if machine_state["input_moisture_pct"] < 1.0:
                    dryness_penalty += 15.0
                    print(f"[PHYSICS M4] Moisture critically low (<1.0%)! Defect rate spiking by +15%.")
                    
                vibration_penalty = max(0, (machine_state["vibration_hz"] - 75.0) * 0.05)
                
                machine_state["defect_rate_pct"] = base_defect + dryness_penalty + vibration_penalty
                
                machine_state["input_buffer_kg"] -= process_amount
                machine_state["output_buffer_pills"] += pills_made
                machine_state["pills_produced"] += pills_made
                machine_state["cycles_completed"] += 1
                
                # Signal to machine5 that pills are ready, then CLEAR buffer (handed off)
                pills_to_send = machine_state["output_buffer_pills"]
                client.publish("factory/events/machine4_pills_ready",
                             json.dumps({"batch_id": active_batch_id, 
                                       "pill_count": pills_to_send,
                                       "defect_rate_pct": machine_state["defect_rate_pct"]}))
                machine_state["output_buffer_pills"] = 0  # Clear after publishing (handed off)
            
            elif machine_state["input_buffer_kg"] == 0:
                machine_state["status"] = "WAITING_INPUT"
        
        # Publish status periodically
        cycle += 1
        if True:
            client.publish("factory/status/machine4", json.dumps(machine_state))

        time.sleep(3)

except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()