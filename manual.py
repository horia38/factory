import paho.mqtt.client as mqtt
import json
import time
import sys

def print_menu(title, options):
    print(f"\n=== {title} ===")
    for idx, opt in enumerate(options, 1):
        print(f"{idx}. {opt['label']}")
    print("0. Exit")
    
    while True:
        try:
            choice = int(input("\nSelect an option: "))
            if choice == 0:
                sys.exit(0)
            if 1 <= choice <= len(options):
                return options[choice - 1]
            print("Invalid choice, try again.")
        except ValueError:
            print("Please enter a valid number.")

def main():
    print("Initializing Manual Override TUI...")
    client = mqtt.Client("ManualControlTUI")
    
    try:
        client.connect("localhost", 1883)
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return

    machines = [
        {"label": "Machine 1 (Dispenser)", "id": "machine1", "params": [
            {"label": "Refill Powder", "action": "refill", "needs_value": False}
        ]},
        {"label": "Machine 2 (Granulator)", "id": "machine2", "params": [
            {"label": "Processing Speed (RPM)", "action": "processing_speed_rpm", "needs_value": True, "type": int}
        ]},
        {"label": "Machine 3 (Dryer)", "id": "machine3", "params": [
            {"label": "Target Heat (°C)", "action": "target_heat_c", "needs_value": True, "type": float}
        ]},
        {"label": "Machine 4 (Pill Press)", "id": "machine4", "params": [
            {"label": "Target Speed (RPM)", "action": "speed_rpm", "needs_value": True, "type": int}
        ]},
        {"label": "Machine 5 (QC Coater)", "id": "machine5", "params": [
            {"label": "Refill Coating", "action": "refill_coating", "needs_value": False}
        ]}
    ]

    while True:
        machine = print_menu("Select Machine to Control", machines)
        
        param = print_menu(f"Select Parameter for {machine['label']}", machine["params"])
        
        payload = {"action": param["action"]}
        
        if param["needs_value"]:
            while True:
                try:
                    val_str = input(f"\nEnter new value for {param['label']}: ")
                    value = param["type"](val_str)
                    payload["value"] = value
                    break
                except ValueError:
                    print(f"Invalid input. Please enter a valid number.")
                    
        topic = f"factory/commands/{machine['id']}"
        print(f"\nSending payload {payload} to {topic}...")
        client.publish(topic, json.dumps(payload))
        print("✓ Command sent successfully!")
        
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting Manual Override TUI...")
        sys.exit(0)
