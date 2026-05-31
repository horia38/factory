import paho.mqtt.client as mqtt
import json
import time
from openai import OpenAI
from datetime import datetime

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
            
            print(f"\n✅ BATCH {batch_id} COMPLETED")
            print(f"   Total pills produced: {total_pills}")
            print(f"   Final defect rate: {defect_rate:.2f}%")
            
    except json.JSONDecodeError:
        pass

def call_ai_optimization():
    """Calls AI to optimize machine parameters based on real factory physics."""
    print("\n[MASTER AGENT] Analyzing production data for optimization...")
    
    system_prompt = """
    You are the Master AI Coordinator for a pharmaceutical pill manufacturing pipeline.
    
    PIPELINE PHYSICS:
    1. Dispenser (M1) → outputs powder to Granulator
    2. Granulator (M2) → converts powder to granules, sends to Dryer
    3. Dryer (M3) → controls heat, affects moisture content
       - CRITICAL: Lower heat = higher moisture, Higher heat = lower moisture
       - Too dry (moisture < 1.5%) + high vibration = crumbly pills (high defects)
    4. Press (M4) → presses pills at variable RPM/vibration
       - CRITICAL: Input moisture and vibration directly affect defect rate
       - Defects = base + (dryness_penalty if moisture < 1.5%) + (vibration_penalty)
    5. QC (M5) → inspects and coats pills, rejects defective ones
    
    YOUR OPTIMIZATION GOAL:
    - Minimize defect rates by optimizing Dryer heat and Press RPM
    - Consider the interconnected physics: dryer output moisture → press defects
    - Provide 2-3 specific, actionable adjustments
    
    RESPONSE FORMAT - ONLY valid JSON:
    {
      "analysis": "Explain the current issue and physics involved",
      "recommendations": [
        {"machine": "machine3", "parameter": "target_heat_c", "current_value": 85, "suggested_value": 90, "reason": "increase to reduce moisture"},
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
    mqtt_client.publish("factory/commands/machine3", json.dumps({"action": "start_batch", "batch_id": current_batch, "target_heat": 85.0}))
    time.sleep(1)
    
    print(f"📤 Publishing start_batch to machine4...")
    mqtt_client.publish("factory/commands/machine4", json.dumps({"action": "start_batch", "batch_id": current_batch, "speed_rpm": 1000}))
    time.sleep(1)
    
    print(f"📤 Publishing start_batch to machine5...")
    mqtt_client.publish("factory/commands/machine5", json.dumps({"action": "start_batch", "batch_id": current_batch}))
    
    print(f"✓ All batch start commands published!")
    
    return current_batch

def apply_optimization(recommendation):
    """Sends optimization commands to machines."""
    machine = recommendation["machine"]
    parameter = recommendation["parameter"]
    suggested_value = recommendation["suggested_value"]
    reason = recommendation["reason"]
    
    if parameter == "target_heat_c":
        mqtt_client.publish("factory/commands/machine3", 
                          json.dumps({"action": "set_heat", "value": suggested_value}))
        print(f"   → Adjusted {machine} {parameter} to {suggested_value} ({reason})")
    
    elif parameter == "speed_rpm":
        mqtt_client.publish("factory/commands/machine4",
                          json.dumps({"action": "set_rpm", "value": suggested_value}))
        print(f"   → Adjusted {machine} {parameter} to {suggested_value} ({reason})")

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
print("Monitoring 5 production machines...")
print("=" * 60)

# --- Main Control Loop ---
try:
    time.sleep(3)  # Wait for machines to connect
    
    batch_wait_time = 0
    optimization_counter = 0
    
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
        
        # Periodically optimize based on data
        optimization_counter += 1
        if optimization_counter % 20 == 0 and batch_history:  # Every ~60 seconds
            print(f"\n📊 PRODUCTION METRICS (Last 3 Batches):")
            for batch in batch_history[-3:]:
                print(f"   {batch['batch_id']}: {batch['total_pills']} pills, {batch['defect_rate_pct']:.2f}% defects")
            
            ai_optimization = call_ai_optimization()
            if ai_optimization:
                print(f"\n[AI ANALYSIS]: {ai_optimization['analysis']}")
                print(f"\n[APPLYING OPTIMIZATIONS]:")
                for rec in ai_optimization["recommendations"]:
                    apply_optimization(rec)
                
                # Wait for changes to take effect
                time.sleep(20)
                optimization_counter = 0
        
        batch_wait_time += 1
        
        # Check if current batch is complete (output buffer has pills and input is empty)
        if "machine5" in factory_state:
            m5 = factory_state["machine5"]
            m4 = factory_state["machine4"]
            if m5["output_buffer_pills"] > 100 and m4["input_buffer_kg"] == 0:
                print("\n🔄 Previous batch processing complete. Starting new batch in 5 seconds...")
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