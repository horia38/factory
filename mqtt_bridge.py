import asyncio
import json
import paho.mqtt.client as mqtt
import websockets
import time

# Shared state to hold latest metrics
factory_state = {
    "machine1": {},
    "machine2": {},
    "machine3": {},
    "machine4": {},
    "machine5": {},
    "alerts": []
}

connected_clients = set()

def on_connect(client, userdata, flags, rc):
    print("Bridge connected to MQTT broker")
    client.subscribe("factory/status/#")
    client.subscribe("factory/events/#")
    client.subscribe("factory/alerts/#")
    client.subscribe("factory/commands/#")

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        
        if topic.startswith("factory/status/machine"):
            machine_num = topic.split("/")[-1]
            factory_state[machine_num] = payload
            
        elif topic.startswith("factory/alerts/") or "batch_completed" in topic or topic.startswith("factory/commands/"):
            if topic.startswith("factory/commands/") and payload.get("action") == "clear_alerts":
                factory_state["alerts"] = []
                return
            elif topic.startswith("factory/commands/") and payload.get("action") == "start_batch":
                pass # Ignore start batch commands as they spam the log
            else:
                alert_msg = {"topic": topic, "payload": payload, "timestamp": time.time()}
                factory_state["alerts"].append(alert_msg)
                if len(factory_state["alerts"]) > 50:
                    factory_state["alerts"].pop(0)
                
    except Exception as e:
        pass

mqtt_client = mqtt.Client("ReactDashboardBridge")
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883)
mqtt_client.loop_start()

async def broadcast_state():
    while True:
        if connected_clients:
            message = json.dumps(factory_state)
            websockets.broadcast(connected_clients, message)
        await asyncio.sleep(0.1)  # 10 Hz update rate

async def handler(websocket):
    connected_clients.add(websocket)
    try:
        await websocket.send(json.dumps(factory_state))
        await websocket.wait_closed()
    except Exception as e:
        print(f"WebSocket Error: {e}")
    finally:
        connected_clients.remove(websocket)

async def main():
    print("Starting WebSocket server on ws://localhost:8080")
    async with websockets.serve(handler, "localhost", 8080):
        await broadcast_state()

if __name__ == "__main__":
    asyncio.run(main())
