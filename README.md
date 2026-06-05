# 🏭 Advanced Factory Simulation - Real Manufacturing Physics

A sophisticated pharmaceutical pill manufacturing pipeline simulation with **realistic material flow**, **interconnected machine physics**, a **React-based Web Dashboard**, and **AI-driven optimization**.

---

## 🎯 Overview

This is NOT a mock factory. This is a **physics-based simulation** where:
- **Materials flow** from machine to machine (powder → granules → dried granules → pills → coated pills)
- **Machine outputs affect downstream quality** (e.g., M2 overheating cascades to M3; M3 moisture affects M4 press defects)
- **Machines physically buffer and bottleneck** if not synchronized properly.
- **AI coordinator** dynamically optimizes parameters based on real production data.
- **Web Dashboard** provides real-time tracking, live physics visualizations, and a complete Manual Control Panel.

---

## 🔄 Production Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                    PHARMACEUTICAL PIPELINE                    │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  [M1]        [M2]         [M3]        [M4]         [M5]       │
│ Powder   →  Granulator  →  Dryer   →  Press    →   QC+Coat   │
│Dispenser     Motor Heat  Temperature  Vibration   Inspection  │
│             Viscosity     Moisture     RPM        Coating     │
│                                       Defects     Rejection   │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

### **Physics & Cascade Engine**
The factory features a complex, interconnected physics engine:
- **M2 Granulator Motor Heat**: Higher RPM generates immense heat. If M2 overheats, it cascades residual heat downstream into the M3 Dryer.
- **M3 Dryer Moisture**: Moisture directly depends on heat. 
- **M4 Press Defects**: High vibration (from high RPM) combined with dry pills (from M3 overheating) results in crumbly pills and massive defect rate spikes.
- **M5 QC Buffer Backlogs**: M5 processes 400 pills per cycle. If M4 produces faster than that, M5 will physically bottleneck, and the input buffer will accumulate in real-time.

---

## 🚀 Getting Started

### **Prerequisites**
- Python 3.8+
- Node.js (for the React Dashboard)
- MQTT Broker (Mosquitto): `sudo apt install mosquitto mosquitto-clients` or download the Windows installer.
- OpenAI API Key

### **1. Setup the Python Virtual Environment**
```bash
python -m venv .venv

# Windows:
.\.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install paho-mqtt openai python-dotenv websockets
```

### **2. Configure Secrets**
Create a `.env` file in the root directory:
```
OPENAI_API_KEY=sk-proj-your-actual-api-key-here
```
*(Note: Never upload your `.env` file to GitHub!)*

### **3. Start the MQTT Broker**
Ensure Mosquitto is running on port 1883.
```bash
mosquitto -v
```

### **4. Start the Factory Backend**
Open multiple terminal tabs (with your `.venv` activated) and run:
```bash
python mqtt_bridge.py       # Required for the Web Dashboard
python machine1_dispenser.py
python machine2_granulator.py
python machine3_dryer.py
python machine4_press.py
python machine5_qc.py
python master_agent.py      # The AI Coordinator
```

### **5. Start the Web Dashboard**
Open a new terminal tab:
```bash
cd dashboard
npm install
npm run dev
```
Open your browser to the local Vite URL (usually `http://localhost:5173`).

---

## 🖥️ Web Dashboard & Control Panel

The React application features two main tabs:
1. **Factory Floor**: A real-time visual representation of the 5 machines, their physical buffers, current sensor readings, and the live Batch Stats (tracking the total pills produced and average defect rate of the operating batch).
2. **Control Panel**: 
   - **Manual Overrides**: Pause machines, refill hoppers, refill coating fluid.
   - **AI Toggle**: Instantly enable or disable the Master AI Agent.
   - **Time Scale Slider**: Accelerate factory physics from 1x to 5x speed for rapid testing!

---

## 🤖 Master AI Agent

When enabled, the Master Agent analyzes the entire factory state every 30 seconds.
- It understands the complex physics (e.g., "Higher RPM on M2 generates more heat which flows into M3").
- It is constrained to change **only one parameter at a time** to prevent chaotic oscillations.
- It optimizes for maximum throughput while keeping defect rates low.
- AI actions light up the machines in the Web Dashboard with a purple "AI Commanded" glow!

---

## 🛠️ Troubleshooting

- **`ModuleNotFoundError: No module named 'dotenv'`**: Make sure you activated your `.venv` before running the python scripts.
- **WebSocket Connection Failed**: Ensure `mqtt_bridge.py` is running, as it bridges the raw MQTT broker to the React dashboard over WebSockets.
- **Processing Stuck at 0**: The factory operates on chunks. Ensure `TIME_SCALE` is set properly and give the machines time to buffer.

---

## 🔒 Security

All API keys are strictly handled via `python-dotenv`. The Git history has been explicitly scrubbed using `git-filter-repo` to ensure no keys or logs exist in past commits. **This repository is perfectly safe to fork and upload to public GitHub.**
