import time
import json
import random
import paho.mqtt.client as mqtt

machine_state = {
    "machine_id": "M5_QC_Coater",
    "status": "IDLE",  # IDLE, INSPECTING, WAITING_INPUT
    "input_buffer_pills": 0,  # Receives pills from machine4
    "input_buffer_capacity_pills": 1000,
    "output_buffer_pills": 0,  # Finished coated pills
    "output_buffer_capacity_pills": 900,
    "defect_rate_input_pct": 0.5,  # From machine4
    "actual_defect_rate_pct": 0.5,  # After QC inspection
    "coating_fluid_liters": 50.0,
    "coating_fluid_capacity_liters": 50.0,
    "inspection_speed_pills_per_minute": 100,
    "coating_effectiveness_pct": 95.0,  # Improves pill durability
    "pills_inspected": 0,
    "pills_rejected": 0,
    "pills_coated": 0,
    "cycles_completed": 0
}

active_batch_id = None
incoming_defect_rate = 0.5

def on_message(client, userdata, msg):
    """Handle commands and events."""
    global active_batch_id, incoming_defect_rate
    
    try:
        topic = msg.topic
        print(f"[DEBUG M5] Received message on topic: {topic}")
        payload = json.loads(msg.payload.decode('utf-8'))
        print(f"[DEBUG M5] Parsed payload: {payload}")
        
        if "commands/machine5" in topic:
            action = payload.get("action")
            print(f"[DEBUG M5] Command action: {action}")
            
            if action == "start_batch":
                active_batch_id = payload.get("batch_id")
                machine_state["status"] = "INSPECTING"
                print(f"\n✓ [M5 COMMAND] Starting batch {active_batch_id}, status now: {machine_state['status']}")
                
            elif action == "refill_coating":
                machine_state["coating_fluid_liters"] = machine_state["coating_fluid_capacity_liters"]
                print(f"\n[M5 COMMAND] Refilled coating fluid to {machine_state['coating_fluid_liters']}L")
                
            elif action == "pause":
                machine_state["status"] = "IDLE"
                print(f"\n[M5 COMMAND] Paused")
                
        elif "machine4_pills_ready" in topic:
            # Machine4 signals pills are ready for QC
            print(f"[DEBUG M5] Received pills_ready event")
            pill_count = payload.get("pill_count", 0)
            defect_rate = payload.get("defect_rate_pct", 0.5)
            incoming_defect_rate = defect_rate
            
            if pill_count > 0:
                transfer = min(pill_count, machine_state["input_buffer_capacity_pills"] - machine_state["input_buffer_pills"])
                machine_state["input_buffer_pills"] += transfer
                machine_state["defect_rate_input_pct"] = defect_rate
                
                # Resume processing if we were waiting for input
                if machine_state["status"] == "WAITING_INPUT" and active_batch_id:
                    machine_state["status"] = "INSPECTING"
                    print(f"[RESUME] Resuming INSPECTING, got {transfer} pills. Defect rate: {defect_rate:.1f}%")
                else:
                    print(f"[INPUT] Received {transfer} pills. Input defect rate: {defect_rate:.1f}%")
                
    except json.JSONDecodeError as e:
        print(f"[ERROR M5] JSON decode failed: {e}")
    except Exception as e:
        print(f"[ERROR M5] Unexpected error in on_message: {e}")

client = mqtt.Client("Machine5_QC")
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("factory/commands/machine5")
client.subscribe("factory/events/machine4_pills_ready")
client.loop_start()

print("Machine 5 (QC & Coater) Powered On...")

try:
    cycle = 0
    while True:
        # Inspect and coat pills if we have input and coating fluid
        if cycle % 20 == 0:  # Debug print every 60 seconds
            print(f"[DEBUG M5] Status={machine_state['status']}, active_batch_id={active_batch_id}, input={machine_state['input_buffer_pills']} pills, output={machine_state['output_buffer_pills']} pills, coating={machine_state['coating_fluid_liters']:.1f}L")
        
        if machine_state["status"] == "INSPECTING" and active_batch_id:
            if machine_state["input_buffer_pills"] > 0 and machine_state["output_buffer_pills"] < machine_state["output_buffer_capacity_pills"] and machine_state["coating_fluid_liters"] > 0:
                
                # Process 50 pills at a time
                pills_to_process = min(50, machine_state["input_buffer_pills"])
                
                # QC inspection: some pills with defects are caught and rejected
                detected_defects = int(pills_to_process * (machine_state["defect_rate_input_pct"] / 100.0))
                
                # Randomness in detection (not all defects caught)
                detected_defects = int(detected_defects * random.uniform(0.7, 1.0))
                pills_passed = pills_to_process - detected_defects
                
                # Coating improves quality: reduces visible defects further
                final_coated_pills = pills_passed
                
                # Consume coating fluid (0.5L per 50 pills)
                coating_usage = 0.5
                machine_state["coating_fluid_liters"] -= coating_usage
                
                machine_state["input_buffer_pills"] -= pills_to_process
                machine_state["output_buffer_pills"] += final_coated_pills
                machine_state["pills_inspected"] += pills_to_process
                machine_state["pills_rejected"] += detected_defects
                machine_state["pills_coated"] += final_coated_pills
                machine_state["actual_defect_rate_pct"] = (machine_state["pills_rejected"] / max(1, machine_state["pills_inspected"])) * 100.0
                machine_state["cycles_completed"] += 1
                
                # Alert if coating fluid is low
                if machine_state["coating_fluid_liters"] < 10.0:
                    client.publish("factory/alerts/machine5_low_coating",
                                 json.dumps({"batch_id": active_batch_id, "remaining_liters": machine_state["coating_fluid_liters"]}))
            
            # Check for batch completion: no more input coming AND finished processing output
            if machine_state["input_buffer_pills"] == 0 and machine_state["output_buffer_pills"] == 0 and machine_state["pills_coated"] > 0:
                # Batch is complete!
                total_pills = machine_state["pills_coated"]
                defect_rate = machine_state["actual_defect_rate_pct"]
                client.publish("factory/events/batch_completed",
                             json.dumps({"batch_id": active_batch_id,
                                       "total_pills": total_pills,
                                       "defect_rate_pct": defect_rate}))
                print(f"\n✅ BATCH {active_batch_id} COMPLETED: {total_pills} pills produced, {defect_rate:.2f}% defect rate")
                active_batch_id = None  # Reset for next batch
                machine_state["status"] = "IDLE"
                machine_state["pills_coated"] = 0  # Reset for next batch
            
            elif machine_state["input_buffer_pills"] == 0:
                machine_state["status"] = "WAITING_INPUT"
            elif machine_state["coating_fluid_liters"] <= 0:
                machine_state["status"] = "IDLE"
        
        # Publish status periodically
        cycle += 1
        if cycle % 2 == 0:
            client.publish("factory/status/machine5", json.dumps(machine_state))

        time.sleep(3)

except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()