import paho.mqtt.client as mqtt
import json
from datetime import datetime

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

machine_colors = {
    "machine1": CYAN,
    "machine2": BLUE,
    "machine3": YELLOW,
    "machine4": GREEN,
    "machine5": RED
}

def format_machine_status(machine_id, data):
    """Format machine status for readable display."""
    color = machine_colors.get(machine_id, RESET)
    
    if "machine1" in machine_id:
        return f"{color}M1 Dispenser{RESET}: Hopper={data.get('hopper_level_kg', 0):.1f}kg, Buffer={data.get('output_buffer_kg', 0):.1f}kg, Status={data.get('status', 'UNKNOWN')}"
    elif "machine2" in machine_id:
        return f"{color}M2 Granulator{RESET}: Input={data.get('input_buffer_kg', 0):.1f}kg, Output={data.get('output_buffer_kg', 0):.1f}kg, Temp={data.get('motor_temp_c', 0):.0f}°C"
    elif "machine3" in machine_id:
        return f"{color}M3 Dryer{RESET}: Heat={data.get('current_heat_c', 0):.0f}°C→{data.get('target_heat_c', 0):.0f}°C, Moisture={data.get('output_moisture_pct', 0):.1f}%"
    elif "machine4" in machine_id:
        return f"{color}M4 Press{RESET}: RPM={data.get('speed_rpm', 0)}, Vibration={data.get('vibration_hz', 0):.1f}Hz, Defect={data.get('defect_rate_pct', 0):.2f}%"
    elif "machine5" in machine_id:
        return f"{color}M5 QC{RESET}: Output={data.get('output_buffer_pills', 0)} pills, Coating={data.get('coating_fluid_liters', 0):.1f}L, Defect={data.get('actual_defect_rate_pct', 0):.2f}%"

def on_message(client, userdata, msg):
    """Process and display incoming messages."""
    topic = msg.topic
    
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Handle status updates
        if "factory/status" in topic:
            machine_name = topic.split("/")[-1]
            formatted = format_machine_status(machine_name, payload)
            print(f"{BOLD}[{timestamp}]{RESET} {formatted}")
        
        # Handle events
        elif "factory/events" in topic:
            if "powder_ready" in topic:
                print(f"{BOLD}[{timestamp}]{RESET} {CYAN}→ M1 has powder ready ({payload.get('amount_kg', 0):.1f}kg){RESET}")
            elif "granules_ready" in topic:
                print(f"{BOLD}[{timestamp}]{RESET} {BLUE}→ M2 has granules ready ({payload.get('amount_kg', 0):.1f}kg){RESET}")
            elif "granules_dried" in topic:
                print(f"{BOLD}[{timestamp}]{RESET} {YELLOW}→ M3 has dried granules ready (Moisture: {payload.get('moisture_pct', 0):.1f}%){RESET}")
            elif "pills_ready" in topic:
                print(f"{BOLD}[{timestamp}]{RESET} {GREEN}→ M4 has pills ready ({payload.get('pill_count', 0)} pills, Defect: {payload.get('defect_rate_pct', 0):.2f}%){RESET}")
            elif "batch_completed" in topic:
                print(f"{BOLD}[{timestamp}]{RESET} {RED}✓ BATCH COMPLETE: {payload.get('batch_id')} - {payload.get('total_pills', 0)} pills (Defect: {payload.get('defect_rate_pct', 0):.2f}%){RESET}")
        
        # Handle alerts
        elif "factory/alerts" in topic:
            if "low_powder" in topic:
                print(f"{BOLD}[{timestamp}]{RESET} {RED}⚠️  ALERT: M1 Low on Powder!{RESET}")
            elif "low_coating" in topic:
                print(f"{BOLD}[{timestamp}]{RESET} {RED}⚠️  ALERT: M5 Low on Coating Fluid!{RESET}")
        
        # Handle commands
        elif "factory/commands" in topic:
            machine = topic.split("/")[-1]
            action = payload.get("action", "unknown")
            print(f"{BOLD}[{timestamp}]{RESET} {BOLD}📤 COMMAND{RESET}: {machine} ← {action}")
            
    except json.JSONDecodeError:
        print(f"{BOLD}[{timestamp}]{RESET} {RED}[ERROR] Malformed JSON{RESET}")

# Setup the listener
client = mqtt.Client("Factory_Monitor")
client.on_message = on_message

print("\n" + "="*80)
print(f"{BOLD}🏭 FACTORY FLOOR MONITORING SYSTEM{RESET}")
print("="*80)
print("Listening to all factory communications...\n")

client.connect("localhost", 1883)

# Subscribe to all factory topics
client.subscribe("factory/status/#")
client.subscribe("factory/events/#")
client.subscribe("factory/alerts/#")
client.subscribe("factory/commands/#")

# Keep listening forever
client.loop_forever()