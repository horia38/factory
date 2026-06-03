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
    
    PIPELINE PHYSICS & FAILURES:
    1. Dispenser (M1) → outputs powder to Granulator
       - CRITICAL FAILURE (trigger_m1_leak.py): Hopper drops to 15kg. M1 feed starves, dispensing is reduced by 30-50%, and M1 shortchanges M2.
    2. Granulator (M2) → converts powder to granules, sends to Dryer
       - CRITICAL: M1 shortchanging M2 causes viscosity spikes (>400cP).
       - CRITICAL FAILURE (trigger_m2_rpm_surge.py): Forces RPM to 1200. High viscosity or RPM surges forces M2 motor to work harder, overheating it (>70C).
    3. Dryer (M3) → controls heat, affects moisture content
       - PARAMETERS YOU CAN CHANGE: target_heat_c (default 80.0)
       - CRITICAL: M2 overheating causes M3's heat to overshoot, dropping moisture critically low (< 1.0%).
       - Backpressure from M4 slowing down prevents M3 from emptying its output buffer, over-baking the granules (moisture drops by 0.5% every cycle).
    4. Press (M4) → presses pills at variable RPM/vibration
       - PARAMETERS YOU CAN CHANGE: speed_rpm (default 1000)
       - CRITICAL: Moisture < 1.0% causes massive defect spikes (+15%).
       - CRITICAL FAILURE (trigger_m4_vibration_jam.py): Forces speed down to 200 RPM, severely slowing consumption and causing backpressure in M3.
    5. QC (M5) → inspects and coats pills, rejects defective ones
    
    YOUR OPTIMIZATION GOAL:
    - Minimize defect rates by optimizing M3 target_heat_c and M4 speed_rpm.
    - Identify if cascading failures (e.g. M1 leak -> M2 overheat -> M3 overbake -> M4 defects) are occurring.
    - Provide 1-2 specific, actionable adjustments. Note that if a failure script is actively overriding a parameter, your changes might be ignored by the hardware, but you should attempt to mitigate via other parameters.
    
    RESPONSE FORMAT - ONLY valid JSON:
    {
      "analysis": "Explain the current issue and physics involved",
      "recommendations": [
        {"machine": "machine3", "parameter": "target_heat_c", "current_value": 80, "suggested_value": 85, "reason": "increase to reduce moisture"},
        {"machine": "machine4", "parameter": "speed_rpm", "current_value": 1000, "suggested_value": 950, "reason": "reduce vibration to improve quality"}
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
    
    # Sequence: Start M1 → M2 → M3 → M4 → M5
    print(f"📤 Publishing start_batch to machine1...")
    mqtt_client.publish("factory/commands/machine1", json.dumps({"action": "start_batch", "batch_id": current_batch}))
    time.sleep(1)
    
    print(f"📤 Publishing start_batch to machine2...")
    mqtt_client.publish("factory/commands/machine2", json.dumps({"action": "start_batch", "batch_id": current_batch}))
    time.sleep(1)
    
    print(f"📤 Publishing start_batch to machine3...")
    mqtt_client.publish("factory/commands/machine3", json.dumps({"action": "start_batch", "batch_id": current_batch, "target_heat": 80.0}))
    time.sleep(1)
    
    print(f"📤 Publishing start_batch to machine4...")
    mqtt_client.publish("factory/commands/machine4", json.dumps({"action": "start_batch", "batch_id": current_batch, "speed_rpm": 1000}))
    time.sleep(1)
    
    print(f"📤 Publishing start_batch to machine5...")
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

# --- Main Control Loop ---
try:
    time.sleep(3)  # Wait for machines to connect
    
    batch_wait_time = 0
    last_ai_call_time = 0
    
    while True:
        # Check if all machines are online
        if len(factory_state) < 5:
            print(f"⏳ Waiting for machines to come online... ({len(factory_state)}/5)")
            print(f"   Online: {list(factory_state.keys())}")
            time.sleep(5)
            continue
        
        # Start first batch
        if current_batch is None:
            print("\n✓ All machines online! Starting production...")
            start_new_batch()
            batch_wait_time = 0
        
        # Check defect rate and speed in real-time from M4
        current_defect_rate = 0.0
        current_speed = 1000
        if "machine4" in factory_state:
            current_defect_rate = factory_state["machine4"].get("defect_rate_pct", 0.0)
            current_speed = factory_state["machine4"].get("speed_rpm", 1000)
            
        current_time = time.time()
        
        # Call AI only if defect rate is high or production is critically low, and cooldown has passed
        if (current_defect_rate > 5.0 or current_speed < 500) and (current_time - last_ai_call_time) >= 60.0:
            if current_speed < 500:
                msg = f"Critically low production detected (M4 Speed: {current_speed} RPM)"
                print(f"\n⚠️ {msg.upper()}. Consulting AI Master Coordinator...")
                mqtt_client.publish("factory/alerts/master_agent", json.dumps({"message": f"Low production detected (Speed: {current_speed} RPM). Consulting AI API..."}))
                append_to_log(f"FACTORY ALERT: {msg}")
            else:
                msg = f"High defect rate detected ({current_defect_rate:.2f}%)"
                print(f"\n⚠️ {msg.upper()}. Consulting AI Master Coordinator...")
                mqtt_client.publish("factory/alerts/master_agent", json.dumps({"message": f"High defect rate detected ({current_defect_rate:.1f}%). Consulting AI API..."}))
                append_to_log(f"FACTORY ALERT: {msg}")
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
        
        batch_wait_time += 1
        
        # Auto-start new batch after completion
        if current_batch is None and len(factory_state) >= 5:
            print("\n⏳ Starting new batch in 3 seconds...")
            time.sleep(3)
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
                    "defect_rate_pct": m5.get("actual_defect_rate_pct", 0.0)
                }))
                
                time.sleep(5)
                start_new_batch()
                batch_wait_time = 0
        
        time.sleep(3)

except KeyboardInterrupt:
    print("\n\n⛔ Shutting down Master Agent...")
    print(f"📈 Total batches completed: {len(batch_history)}")
    if batch_history:
        avg_defect = sum(b["defect_rate_pct"] for b in batch_history) / len(batch_history)
        print(f"📉 Average defect rate: {avg_defect:.2f}%")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()