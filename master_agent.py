import paho.mqtt.client as mqtt
import json
import time
import os
import glob
from openai import OpenAI
from datetime import datetime

os.makedirs('logs', exist_ok=True)
existing_logs = glob.glob('logs/log*.txt')
if not existing_logs:
    log_file_path = 'logs/log01.txt'
else:
    nums = []
    for f in existing_logs:
        try:
            fname = os.path.basename(f)
            num_str = fname.replace('log', '').replace('.txt', '')
            nums.append(int(num_str))
        except:
            pass
    next_num = max(nums) + 1 if nums else 1
    log_file_path = f'logs/log{next_num:02d}.txt'

def append_to_log(message):
    try:
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception as e:
        print(f"Failed to write log: {e}")

append_to_log("Master AI Agent Started")

# --- OpenAI Setup ---
OPENAI_API_KEY = "[REDACTED_API_KEY]"
ai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- Factory State Memory ---
factory_state = {}
batch_counter = 1
current_batch = None
batch_history = []

def on_message(client, userdata, msg):
    """Updates factory state from machine status broadcasts."""
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        
        # Extract machine name from topic (e.g., "factory/status/machine1" -> "machine1")
        parts = topic.split("/")
        if "status" in parts:
            machine_name = parts[-1]
            factory_state[machine_name] = payload
        
        # Handle critical alerts
        if "low_powder" in topic:
            print(f"\n⚠️  ALERT: {payload}")
            client.publish("factory/commands/machine1", json.dumps({"action": "refill"}))
        
        if "low_coating" in topic:
            print(f"\n⚠️  ALERT: {payload}")
            client.publish("factory/commands/machine5", json.dumps({"action": "refill_coating"}))
        
        # Track batch completion
        if "batch_completed" in topic:
            batch_id = payload.get("batch_id")
            defect_rate = payload.get("defect_rate_pct", 0)
            total_pills = payload.get("total_pills", 0)
            
            batch_history.append({
                "batch_id": batch_id,
                "defect_rate_pct": defect_rate,
                "total_pills": total_pills,
                "timestamp": datetime.now().isoformat()
            })
            
            print(f"\n{'='*60}")
            print(f"✅ BATCH {batch_id} COMPLETED")
            print(f"   Total pills produced: {total_pills}")
            print(f"   Final defect rate: {defect_rate:.2f}%")
            print(f"{'='*60}")
            
            append_to_log(f"BATCH COMPLETED: {batch_id} | Total Pills: {total_pills} | Final Defect Rate: {defect_rate:.2f}%")
            
            # Schedule next batch
            current_batch = None  # Reset so new batch will start on next cycle
            
    except json.JSONDecodeError:
        pass

def call_ai_optimization():
    """Calls AI to optimize machine parameters based on real factory physics."""
    print("\n[MASTER AGENT] Analyzing production data for optimization...")
    
    system_prompt = """
    You are the Master AI Coordinator for a pharmaceutical pill manufacturing pipeline.
    
    PIPELINE PHYSICS:
    1. Dispenser (M1) → outputs powder to Granulator.
    2. Granulator (M2) → converts powder to granules, sends to Dryer. Motor heat and viscosity fluctuate dynamically based on flow rates.
       - PARAMETERS YOU CAN CHANGE: processing_speed_rpm
    3. Dryer (M3) → controls heat, affects moisture content.
       - PARAMETERS YOU CAN CHANGE: target_heat_c
    4. Press (M4) → presses pills at variable RPM/vibration.
       - PARAMETERS YOU CAN CHANGE: speed_rpm
    5. QC (M5) → inspects and coats pills, rejects defective ones.
    
    YOUR OPTIMIZATION GOAL:
    - Minimize defect rates and maximize production volume by optimizing parameters on M2, M3, and M4.
    - Identify if cascading bottlenecks are occurring based on the live physics data.
    - Provide 1-2 specific, actionable adjustments. If a hardware constraint overrides a parameter, attempt to mitigate via other parameters.
    
    RESPONSE FORMAT - ONLY valid JSON:
    {
      "analysis": "Explain the current issue and physics involved",
      "recommendations": [
        {"machine": "machineX", "parameter": "param_name", "suggested_value": 0, "reason": "why"}
      ]
    }
    """

    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Current Factory State: {json.dumps(factory_state)}\n\nBatch History: {json.dumps(batch_history[-5:] if batch_history else [])}"}
            ]
        )
        
        result_str = response.choices[0].message.content
        return json.loads(result_str)
        
    except Exception as e:
        print(f"[ERROR] AI Call Failed: {e}")
        return None

def start_new_batch():
    """Initiates a new production batch through the entire pipeline."""
    global current_batch, batch_counter
    
    current_batch = f"BATCH_{batch_counter:03d}"
    batch_counter += 1
    
    print(f"\n{'='*60}")
    print(f"🏭 STARTING NEW BATCH: {current_batch}")
    print(f"{'='*60}")
    
    # Don't reset AI optimized parameters (speed_rpm, target_heat_c), just start the batch
    mqtt_client.publish("factory/commands/machine1", json.dumps({"action": "start_batch", "batch_id": current_batch}))
    time.sleep(1)
    mqtt_client.publish("factory/commands/machine2", json.dumps({"action": "start_batch", "batch_id": current_batch}))
    time.sleep(1)
    mqtt_client.publish("factory/commands/machine3", json.dumps({"action": "start_batch", "batch_id": current_batch}))
    time.sleep(1)
    mqtt_client.publish("factory/commands/machine4", json.dumps({"action": "start_batch", "batch_id": current_batch}))
    time.sleep(1)
    mqtt_client.publish("factory/commands/machine5", json.dumps({"action": "start_batch", "batch_id": current_batch}))
    
    print(f"✓ All batch start commands published!")
    
    return current_batch

def apply_optimization(rec):
    machine = rec.get("machine")
    action = rec.get("parameter") or rec.get("action")
    value = rec.get("suggested_value") or rec.get("value")
    
    if machine and action and value is not None:
        print(f"   → Adjusted {machine} {action} to {value}")
        mqtt_client.publish(f"factory/commands/{machine}", json.dumps({"action": action, "value": value}))
        mqtt_client.publish("factory/alerts/master_agent", json.dumps({"message": f"Issued command to {machine}: Set {action} = {value}"}))
        append_to_log(f"ACTION TAKEN: Sent {action}={value} to {machine}")

# --- MQTT Setup ---
mqtt_client = mqtt.Client("MasterAgent")
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883)
mqtt_client.subscribe("factory/status/#")
mqtt_client.subscribe("factory/events/#")
mqtt_client.subscribe("factory/alerts/#")
mqtt_client.loop_start()

print("\n" + "="*60)
print("🤖 MASTER AI AGENT ONLINE - FACTORY COORDINATION SYSTEM")
print("="*60)

# Clear the web UI logs on startup
mqtt_client.publish("factory/commands/master_agent", json.dumps({"action": "clear_alerts"}))

print("Monitoring 5 production machines...")
print("=" * 60)

def main():
    global last_ai_call_time, high_defect_start_time, low_production_start_time, m5_output_history, current_batch, batch_wait_time
    last_ai_call_time = 0
    batch_wait_time = 0
    high_defect_start_time = None
    low_production_start_time = None
    m5_output_history = []
    
    # Send clear_alerts command to UI on startup
    mqtt_client.publish("factory/alerts/master_agent", json.dumps({"action": "clear_alerts"}))
    append_to_log("SYSTEM STARTUP: Master Agent initialized, alerts cleared.")
    
    start_new_batch()
    
    try:
        while True:
            time.sleep(1)
            current_time = time.time()
            
            # Track M5 Output for Production Rate (OPS)
            current_pills = 0
            if "machine5" in factory_state:
                current_pills = factory_state["machine5"].get("pills_coated", 0)
            
            m5_output_history.append((current_time, current_pills))
            # Keep rolling window of 60 seconds
            m5_output_history = [x for x in m5_output_history if current_time - x[0] <= 60.0]
            
            ops_60s = 0.0
            ops_5s = 0.0
            is_low_production = False
            
            if len(m5_output_history) > 1:
                oldest = m5_output_history[0]
                if current_time - oldest[0] > 0:
                    ops_60s = (current_pills - oldest[1]) / (current_time - oldest[0])
                    
                # Find entry from ~5 seconds ago
                five_sec_ago = [x for x in m5_output_history if current_time - x[0] <= 5.0]
                if five_sec_ago:
                    ref = five_sec_ago[0]
                    if current_time - ref[0] > 0:
                        ops_5s = (current_pills - ref[1]) / (current_time - ref[0])
            
            # Check for low production ONLY if we have at least 15 seconds of baseline
            if len(m5_output_history) > 1 and (current_time - m5_output_history[0][0]) >= 15.0:
                if ops_60s > 0 and ops_5s < (ops_60s * 0.5):
                    is_low_production = True
            
            # Monitor states for anomalies
            trigger_ai = False
            alert_msg_text = ""
            
            current_defect_rate = factory_state.get("machine5", {}).get("actual_defect_rate_pct", 0)
            
            # Update timers
            if current_defect_rate > 5.0:
                if high_defect_start_time is None:
                    high_defect_start_time = current_time
            else:
                high_defect_start_time = None
                
            if is_low_production:
                if low_production_start_time is None:
                    low_production_start_time = current_time
            else:
                low_production_start_time = None

            # Check if condition persisted for 5 seconds
            if high_defect_start_time and (current_time - high_defect_start_time) >= 5.0:
                trigger_ai = True
                alert_msg_text = f"High defect rate detected ({current_defect_rate:.2f}%) persisting > 5s"
                
            elif low_production_start_time and (current_time - low_production_start_time) >= 5.0:
                trigger_ai = True
                alert_msg_text = f"Critically low production detected (5s OPS: {ops_5s:.1f} vs 60s avg: {ops_60s:.1f}) persisting > 5s"

            if trigger_ai and (current_time - last_ai_call_time) >= 60.0:
                print(f"\n⚠️ {alert_msg_text}. Consulting AI API...")
                mqtt_client.publish("factory/alerts/master_agent", json.dumps({"message": f"{alert_msg_text}. Consulting AI API..."}))
                append_to_log(f"FACTORY ALERT: {alert_msg_text}")
                
                print(f"\n📊 PRODUCTION METRICS (Last 3 Batches):")
                if batch_history:
                    for batch in batch_history[-3:]:
                        print(f"   {batch['batch_id']}: {batch['total_pills']} pills, {batch['defect_rate_pct']:.2f}% defects")
                else:
                    print(f"   No batches completed yet.")
                
                append_to_log("AI CALL: Requesting optimization analysis from Master Coordinator...")
                ai_optimization = call_ai_optimization()
                last_ai_call_time = time.time()
                
                if ai_optimization:
                    append_to_log(f"AI RESPONSE: Analysis completed -> {ai_optimization.get('analysis', '')}")
                    print(f"\n[AI ANALYSIS]: {ai_optimization['analysis']}")
                    mqtt_client.publish("factory/alerts/master_agent", json.dumps({"message": f"AI ANALYSIS: {ai_optimization['analysis']}"}))
                    print(f"\n[APPLYING OPTIMIZATIONS]:")
                    for rec in ai_optimization.get("recommendations", []):
                        apply_optimization(rec)
            
            # -- Loop continuation code for batching --
            batch_wait_time += 1
            
            # Auto-start new batch after completion
            if current_batch is None and len(factory_state) >= 5:
                if batch_wait_time % 3 == 0:
                    print("\n⏳ Starting new batch...")
                    start_new_batch()
                    batch_wait_time = 0
            
            # Check if current batch is complete: pipeline empty and pills coated
            if current_batch is not None and "machine5" in factory_state:
                m5 = factory_state["machine5"]
                m4 = factory_state["machine4"]
                m3 = factory_state.get("machine3", {"output_buffer_kg": 0, "input_buffer_kg": 0})
                m2 = factory_state.get("machine2", {"output_buffer_kg": 0, "input_buffer_kg": 0})
                m1 = factory_state.get("machine1", {"output_buffer_kg": 0, "batch_dispensed_kg": 0.0})
                
                # Since M1 stops after dispensing 20kg, eventually everything else empties out
                if (m5["pills_coated"] > 0 and 
                    m5["input_buffer_pills"] == 0 and 
                    m4["input_buffer_kg"] == 0 and m4.get("output_buffer_pills", 0) == 0 and
                    m3["input_buffer_kg"] == 0 and m3["output_buffer_kg"] == 0 and
                    m2["input_buffer_kg"] == 0 and m2["output_buffer_kg"] == 0 and
                    m1["output_buffer_kg"] == 0 and 
                    m1.get("batch_dispensed_kg", 0.0) >= 20.0):
                    
                    print(f"\n🔄 Pipeline empty. Batch {current_batch} processing complete!")
                    
                    # Manually trigger batch_completed event for the system
                    mqtt_client.publish("factory/events/batch_completed", json.dumps({
                        "batch_id": current_batch,
                        "total_pills": m5["pills_coated"],
                        "defect_rate_pct": m5.get("actual_defect_rate_pct", 0)
                    }))

    except KeyboardInterrupt:
    print("\n\n⛔ Shutting down Master Agent...")
    print(f"📈 Total batches completed: {len(batch_history)}")
    if batch_history:
        avg_defect = sum(b["defect_rate_pct"] for b in batch_history) / len(batch_history)
        print(f"📉 Average defect rate: {avg_defect:.2f}%")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()