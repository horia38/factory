import time
import json
import random
import paho.mqtt.client as mqtt

machine_state = {
    "machine_id": "M3_Dryer",
    "status": "IDLE",  # IDLE, DRYING, WAITING_INPUT
    "input_buffer_kg": 0.0,  # Receives granules from machine2
    "input_buffer_capacity_kg": 20.0,
    "output_buffer_kg": 0.0,  # Sends dried granules to machine4
    "output_buffer_capacity_kg": 15.0,
    "target_heat_c": 80.0,
    "current_heat_c": 25.0,
    "moisture_content_pct": 5.0,
    "output_moisture_pct": 2.0,  # Moisture after drying (affects pill quality)
    "cycles_completed": 0
}

active_batch_id = None

def on_message(client, userdata, msg):
    """Handle commands and events."""
    global active_batch_id
    
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode('utf-8'))
        
        if "commands/machine3" in topic:
            action = payload.get("action")
            
            if action == "start_batch":
                active_batch_id = payload.get("batch_id")
                machine_state["status"] = "DRYING"
                machine_state["target_heat_c"] = payload.get("target_heat", 80.0)
                print(f"\n✓ [M3 COMMAND] Starting batch {active_batch_id}, target heat: {machine_state['target_heat_c']}C, status now: {machine_state['status']}")
                
            elif action in ("set_heat", "target_heat_c"):
                machine_state["target_heat_c"] = payload.get("value", 80.0)
                print(f"\n[M3 COMMAND] Adjusting heat to {machine_state['target_heat_c']}C")
                
            elif action == "pause":
                machine_state["status"] = "IDLE"
                print(f"\n[M3 COMMAND] Paused")
                
        elif "machine2_granules_ready" in topic:
            # Machine2 signals granules are available
            amount = payload.get("amount_kg", 0)
            incoming_temp = payload.get("motor_temp_c", 55.0)
            
            # PHYSICS: Thermal Cascade
            if incoming_temp > 70.0:
                overshoot = (incoming_temp - 70.0) * 1.5
                machine_state["current_heat_c"] = machine_state["target_heat_c"] + overshoot
                print(f"[PHYSICS M3] Incoming granules too hot ({incoming_temp}C)! Heat overshooting to {machine_state['current_heat_c']}C")
                
            if amount > 0:
                transfer = min(amount, machine_state["input_buffer_capacity_kg"] - machine_state["input_buffer_kg"])
                if transfer > 0:
                    machine_state["input_buffer_kg"] += transfer
                    machine_state["moisture_content_pct"] = 5.0 + random.uniform(-0.5, 0.5)
                    
                    if machine_state["status"] == "WAITING_INPUT" and active_batch_id:
                        machine_state["status"] = "DRYING"
                        print(f"[RESUME] Resuming DRYING, got {transfer} kg granules")
                    else:
                        print(f"[INPUT] Received {transfer} kg granules. Moisture: {machine_state['moisture_content_pct']:.1f}%")
                    
        elif "machine4_consumed" in topic:
            consumed = payload.get("consumed_kg", 0)
            machine_state["output_buffer_kg"] = max(0.0, machine_state["output_buffer_kg"] - consumed)
                
    except json.JSONDecodeError as e:
        print(f"[ERROR M3] JSON decode failed: {e}")
    except Exception as e:
        print(f"[ERROR M3] Unexpected error in on_message: {e}")

client = mqtt.Client("Machine3_Dryer")
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("factory/commands/machine3")
client.subscribe("factory/events/machine2_granules_ready")
client.subscribe("factory/events/machine4_consumed")
client.loop_start()

print("Machine 3 (Dryer) Powered On...")

try:
    cycle = 0
    while True:
        # Ramp temperature toward target
        if cycle % 20 == 0:  # Debug print every 60 seconds
            print(f"[DEBUG M3] Status={machine_state['status']}, active_batch_id={active_batch_id}, heat={machine_state['current_heat_c']:.1f}°C→{machine_state['target_heat_c']:.1f}°C, input={machine_state['input_buffer_kg']:.1f}kg")
        
        if machine_state["current_heat_c"] < machine_state["target_heat_c"]:
            machine_state["current_heat_c"] = min(machine_state["current_heat_c"] + 2.0, machine_state["target_heat_c"])
        elif machine_state["current_heat_c"] > machine_state["target_heat_c"]:
            machine_state["current_heat_c"] = max(machine_state["current_heat_c"] - 1.0, machine_state["target_heat_c"])
        
        # Dry granules if we have input and heat is up
        if machine_state["status"] == "DRYING" and active_batch_id:
            if machine_state["input_buffer_kg"] > 0 and machine_state["output_buffer_kg"] < machine_state["output_buffer_capacity_kg"]:
                # Drying process: consume input, output drier material
                dry_amount = min(1.0, machine_state["input_buffer_kg"])
                
                # Physics: Higher heat = lower moisture in output
                # Base moisture decreases as heat increases
                base_moisture = 10.0 - (machine_state["current_heat_c"] - 25.0) * 0.15
                machine_state["output_moisture_pct"] = max(0.5, base_moisture + random.uniform(-0.3, 0.3))
                
                machine_state["input_buffer_kg"] -= dry_amount
                machine_state["output_buffer_kg"] += dry_amount
                machine_state["cycles_completed"] += 1
            
            elif machine_state["input_buffer_kg"] == 0 and machine_state["output_buffer_kg"] == 0:
                machine_state["status"] = "WAITING_INPUT"
                
            if machine_state["output_buffer_kg"] > 0:
                # PHYSICS: Backpressure time penalty
                machine_state["output_moisture_pct"] = max(0.0, machine_state["output_moisture_pct"] - 0.5)
                if machine_state["output_moisture_pct"] < 1.0:
                    print(f"[PHYSICS M3] Backpressure! Granules over-baking in buffer. Moisture dropped to {machine_state['output_moisture_pct']:.1f}%")
                
                client.publish("factory/events/machine3_granules_dried",
                             json.dumps({"batch_id": active_batch_id, 
                                       "amount_kg": machine_state["output_buffer_kg"],
                                       "moisture_pct": machine_state["output_moisture_pct"]}))
        
        # Publish status periodically
        cycle += 1
        if True:
            client.publish("factory/status/machine3", json.dumps(machine_state))

        time.sleep(3)

except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()