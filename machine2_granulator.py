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
        print(f"[DEBUG M2] Received message on topic: {topic}")
        payload = json.loads(msg.payload.decode('utf-8'))
        print(f"[DEBUG M2] Parsed payload: {payload}")
        
        if "commands/machine2" in topic:
            action = payload.get("action")
            print(f"[DEBUG M2] Command action: {action}")
            
            if action == "start_batch":
                active_batch_id = payload.get("batch_id")
                machine_state["status"] = "PROCESSING"
                print(f"\n✓ [M2 COMMAND] Starting batch {active_batch_id}, status now: {machine_state['status']}")
                
            elif action == "pause":
                machine_state["status"] = "IDLE"
                print(f"\n[M2 COMMAND] Paused")
                
        elif "machine1_powder_ready" in topic:
            # Machine1 signals that powder is available
            print(f"[DEBUG M2] Received powder_ready event")
            amount = payload.get("amount_kg", 0)
            if amount > 0:
                transfer = min(amount, machine_state["input_buffer_capacity_kg"] - machine_state["input_buffer_kg"])
                machine_state["input_buffer_kg"] += transfer
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
                # Granulate: consume input, produce output (granules are more volume-dense)
                process_amount = min(machine_state["batch_size_kg"], machine_state["input_buffer_kg"])
                granule_output = process_amount * 0.95  # 95% efficiency
                
                machine_state["input_buffer_kg"] -= process_amount
                machine_state["output_buffer_kg"] += granule_output
                machine_state["processing_speed_rpm"] = random.randint(750, 850)
                machine_state["motor_temp_c"] = round(random.uniform(55.0, 75.0), 1)
                machine_state["viscosity_cp"] = round(random.uniform(340.0, 410.0), 1)
                machine_state["cycles_completed"] += 1
                
                # Signal to machine3 that granules are ready, then CLEAR buffer (handed off)
                amount_to_send = machine_state["output_buffer_kg"]
                client.publish("factory/events/machine2_granules_ready",
                             json.dumps({"batch_id": active_batch_id, "amount_kg": amount_to_send}))
                machine_state["output_buffer_kg"] = 0  # Clear after publishing (handed off)
            
            elif machine_state["input_buffer_kg"] == 0:
                machine_state["status"] = "WAITING_INPUT"
        
        # Publish status periodically
        cycle += 1
        if cycle % 2 == 0:
            client.publish("factory/status/machine2", json.dumps(machine_state))

        time.sleep(3)

except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()