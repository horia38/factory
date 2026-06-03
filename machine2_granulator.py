import time
import json
import random
import paho.mqtt.client as mqtt

machine_state = {
    "machine_id": "M2_Granulator",
    "status": "IDLE",  # IDLE, PROCESSING, WAITING_INPUT, RUNNING
    "input_buffer_kg": 0.0,  # Receives from machine1
    "input_buffer_capacity_kg": 25.0,
    "output_buffer_kg": 0.0,  # Sends to machine3
    "output_buffer_capacity_kg": 20.0,
    "motor_temp_c": 25.0,
    "viscosity_cp": 350.0,
    "processing_speed_rpm": 800,
    "batch_size_kg": 5.0,
    "cycles_completed": 0
}

active_batch_id = None

def on_message(client, userdata, msg):
    """Handle commands from master or status updates from machine1."""
    global active_batch_id
    
    try:
        topic = msg.topic
        
        if "triggers/m2_rpm_surge" in topic:
            machine_state["processing_speed_rpm"] = 1200
            machine_state["surge_timer"] = 10
            print(f"\n[M2 TRIGGER] RPM Surge triggered! Speed forced to 1200 RPM for 30 seconds.")
            return
            
        payload = json.loads(msg.payload.decode('utf-8'))
        
        if "commands/machine2" in topic:
            action = payload.get("action")
            
            if action == "start_batch":
                active_batch_id = payload.get("batch_id")
                machine_state["status"] = "PROCESSING"
                print(f"\n✓ [M2 COMMAND] Starting batch {active_batch_id}, status now: {machine_state['status']}")
                
            elif action == "pause":
                machine_state["status"] = "IDLE"
                print(f"\n[M2 COMMAND] Paused")
                
        elif "machine1_powder_ready" in topic:
            # Machine1 signals that powder is available
            amount = payload.get("amount_kg", 0)
            if amount > 0:
                transfer = min(amount, machine_state["input_buffer_capacity_kg"] - machine_state["input_buffer_kg"])
                machine_state["input_buffer_kg"] += transfer
                if machine_state["status"] == "WAITING_INPUT":
                    machine_state["status"] = "PROCESSING"
                print(f"[INPUT] Received {transfer} kg from Dispenser. Buffer: {machine_state['input_buffer_kg']} kg")
                
    except json.JSONDecodeError as e:
        print(f"[ERROR M2] JSON decode failed: {e}")
    except Exception as e:
        print(f"[ERROR M2] Unexpected error in on_message: {e}")

client = mqtt.Client("Machine2_Granulator")
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("factory/commands/machine2")
client.subscribe("factory/events/machine1_powder_ready")
client.subscribe("factory/triggers/m2_rpm_surge")
client.loop_start()

print("Machine 2 (Granulator) Powered On...")

try:
    cycle = 0
    while True:
        if cycle % 20 == 0:  # Debug print every 60 seconds
            print(f"[DEBUG M2] Status={machine_state['status']}, active_batch_id={active_batch_id}, input={machine_state['input_buffer_kg']:.1f}kg, output={machine_state['output_buffer_kg']:.1f}kg")
        
        # Process powder if we have input and we're active
        if machine_state["status"] == "PROCESSING" and active_batch_id:
            if machine_state["input_buffer_kg"] > 0 and machine_state["output_buffer_kg"] < machine_state["output_buffer_capacity_kg"]:
                # Processing speed
                max_process = min(1.0, machine_state["input_buffer_kg"])
                process_amount = max_process
                
                # PHYSICS: Viscosity Spike due to Feed Starvation
                # If incoming powder is unexpectedly low, ratio of liquid binder to powder is too high
                expected_amount = 1.0
                actual_amount = process_amount
                
                if actual_amount < expected_amount - 0.2:
                    # Not enough powder -> too much liquid -> viscosity spikes!
                    machine_state["viscosity_cp"] = min(800.0, 350.0 / actual_amount)
                    machine_state["processing_speed_rpm"] = random.randint(750, 850)
                
                # PHYSICS: Viscosity calculation based on input amount
                machine_state["viscosity_cp"] = round(350.0 / max(0.1, process_amount), 1)
                
                granule_output = process_amount * 0.95  # 95% efficiency
                
                machine_state["input_buffer_kg"] -= process_amount
                machine_state["output_buffer_kg"] += granule_output
                
                # Manage temporary RPM surge
                if machine_state.get("surge_timer", 0) > 0:
                    machine_state["processing_speed_rpm"] = 1200
                    machine_state["surge_timer"] -= 1
                else:
                    machine_state["processing_speed_rpm"] = random.randint(750, 850)
                
                # PHYSICS: Motor temp increases if viscosity > 400cP or RPM is high
                target_temp = 55.0 + (machine_state["processing_speed_rpm"] - 750) * 0.05
                viscosity_penalty = 15.0 if machine_state["viscosity_cp"] > 400.0 else 0.0
                target_temp += viscosity_penalty
                
                # Smooth temperature changes (heats quickly, cools slowly)
                current_temp = machine_state["motor_temp_c"]
                if current_temp < target_temp:
                    machine_state["motor_temp_c"] = round(min(target_temp, current_temp + 3.0) + random.uniform(-0.5, 0.5), 1)
                elif current_temp > target_temp:
                    machine_state["motor_temp_c"] = round(max(target_temp, current_temp - 1.0) + random.uniform(-0.5, 0.5), 1)
                else:
                    machine_state["motor_temp_c"] = round(target_temp + random.uniform(-0.5, 0.5), 1)
                
                if viscosity_penalty > 0:
                    print(f"[PHYSICS M2] Viscosity spike ({machine_state['viscosity_cp']} cP) from low input! Motor temp raised by +15C to {machine_state['motor_temp_c']}C.")
                    
                machine_state["cycles_completed"] += 1
                
                # Signal to machine3 that granules are ready, then CLEAR buffer (handed off)
                amount_to_send = machine_state["output_buffer_kg"]
                client.publish("factory/events/machine2_granules_ready",
                             json.dumps({"batch_id": active_batch_id, "amount_kg": amount_to_send, "motor_temp_c": machine_state["motor_temp_c"]}))
                machine_state["output_buffer_kg"] = 0  # Clear after publishing (handed off)
            
            elif machine_state["input_buffer_kg"] == 0:
                machine_state["status"] = "WAITING_INPUT"
        
        # Publish status periodically
        cycle += 1
        if True:
            client.publish("factory/status/machine2", json.dumps(machine_state))

        time.sleep(3)

except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()