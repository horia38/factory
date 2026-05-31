# 🏭 Advanced Factory Simulation - Real Manufacturing Physics

A sophisticated pharmaceutical pill manufacturing pipeline simulation with **realistic material flow**, **interconnected machine physics**, and **AI-driven optimization**.

---

## 🎯 Overview

This is NOT a mock factory. This is a **physics-based simulation** where:
- **Materials flow** from machine to machine (powder → granules → dried granules → pills → coated pills)
- **Machine outputs affect downstream quality** (dryer moisture → press defects)
- **Machines only process when they have input** (realistic workflow)
- **AI coordinator** dynamically optimizes parameters based on real production data
- **Interconnected systems** where physics constraints drive optimization

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

### **Machine Details**

#### **Machine 1: Powder Dispenser (M1)**
- **Input**: Raw powder hopper (100 kg capacity)
- **Output**: Powder buffer for granulator
- **States**: IDLE, DISPENSING, LOW_POWDER, REFILLING
- **Key Metrics**: Hopper level, dispensing rate, output buffer
- **Physics**: Consumes powder at fixed rate when active

#### **Machine 2: Granulator (M2)**
- **Input**: Powder from M1's output buffer
- **Output**: Granules to dryer
- **States**: IDLE, PROCESSING, WAITING_INPUT
- **Key Metrics**: Motor temperature, viscosity, RPM
- **Physics**: Converts powder to granules (95% efficiency), only processes with input

#### **Machine 3: Dryer (M3)** ⭐ CRITICAL
- **Input**: Granules from M2
- **Output**: Dried granules to press
- **Key Parameters**: 
  - `target_heat_c`: Temperature setpoint (25°C - 100°C)
  - `current_heat_c`: Actual temperature (ramps gradually)
- **Critical Physics**: 
  - **LOWER heat → HIGHER moisture** (base_moisture = 10.0 - (heat - 25) × 0.15)
  - Higher moisture = better pill binding
  - **HIGHER heat → LOWER moisture** = risk of crumbling at high vibration
- **Affects**: Downstream pill quality and defect rates

#### **Machine 4: Pill Press (M4)** ⭐ CRITICAL
- **Input**: Dried granules from M3
- **Output**: Pills to QC machine
- **Key Parameters**:
  - `speed_rpm`: Press speed (typically 800-1200 RPM)
  - `vibration_hz`: Derived from speed
- **Critical Physics**:
  ```
  defect_rate = base_defect + dryness_penalty + vibration_penalty
  
  dryness_penalty = 0 if moisture ≥ 1.5%
                  else (1.5 - moisture) × 3.0
  vibration_penalty = max(0, (vibration_hz - 75.0) × 0.05)
  ```
  - **Too dry + High vibration = Crumbly pills** (HIGH defects)
  - **Proper moisture + Moderate vibration = Good quality**
- **Output**: Pills with defect rate attached
- **Produces**: ~200 pills per kg of granules

#### **Machine 5: QC & Coater (M5)**
- **Input**: Pills from M4
- **Output**: Coated, inspected pills (or rejected)
- **Processes**:
  1. Inspects pills for defects (catches ~70-100% of actual defects)
  2. Coats passing pills with protective layer
  3. Tracks overall defect rate
- **Key Metrics**: Inspection rate, coating fluid level, actual defect rate
- **Physics**: Coating fluid consumption (0.5L per 50 pills)

---

## 🔌 Communication Protocol

### **Topics**

#### Status Updates (Every 6 seconds)
```
factory/status/machine1  → Powder dispenser state
factory/status/machine2  → Granulator state
factory/status/machine3  → Dryer state
factory/status/machine4  → Press state
factory/status/machine5  → QC state
```

#### Event Notifications (Material Ready)
```
factory/events/machine1_powder_ready      → M1: Powder available
factory/events/machine2_granules_ready    → M2: Granules ready
factory/events/machine3_granules_dried    → M3: Dried granules (includes moisture %)
factory/events/machine4_pills_ready       → M4: Pills ready (includes defect rate)
factory/events/batch_completed            → M5: Batch finished
```

#### Commands (Master → Machine)
```
factory/commands/machine1  ← start_batch, pause, refill
factory/commands/machine2  ← start_batch, pause
factory/commands/machine3  ← start_batch, set_heat, pause
factory/commands/machine4  ← start_batch, set_rpm, pause
factory/commands/machine5  ← start_batch, refill_coating, pause
```

#### Alerts
```
factory/alerts/machine1_low_powder   → Hopper needs refilling
factory/alerts/machine5_low_coating  → Coating fluid low
```

---

## 🤖 Master AI Agent

### **Responsibilities**

1. **Workflow Coordination**
   - Triggers sequential machine starts for each batch
   - Monitors pipeline progress
   - Initiates new batches automatically

2. **Real-Time Optimization**
   - Analyzes production metrics every ~60 seconds
   - Calls OpenAI with factory state + physics constraints
   - Applies AI-recommended adjustments to Dryer heat and Press RPM

3. **Performance Tracking**
   - Maintains batch history with defect rates
   - Calculates average defect rate across batches
   - Reports production metrics

### **AI Decision Making**

The AI receives:
- **Current state** of all 5 machines
- **Physics rules** (how temperature affects moisture, how moisture affects defects)
- **Recent batch history** (previous 5 batches' defect rates)

The AI returns JSON with:
- **Analysis**: Understanding of current issue
- **Recommendations**: 2-3 specific parameter adjustments with reasoning

---

## ⚙️ Physics Engine

### **Temperature Dynamics (Dryer)**
```python
# Temperature ramps toward target at 1-2°C per cycle
if current_heat < target_heat:
    current_heat += 2.0 (max toward target)
elif current_heat > target_heat:
    current_heat -= 1.0
```

### **Moisture Calculation (Dryer)**
```python
base_moisture = 10.0 - (current_heat_c - 25.0) * 0.15

# Example physics:
# At 25°C:  base_moisture = 10.0% (very wet)
# At 85°C:  base_moisture = 1.0% (dry)
# At 100°C: base_moisture = -0.5% → clamped to 0.5% (very dry)

output_moisture = max(0.5, base_moisture + random.uniform(-0.3, 0.3))
```

### **Defect Rate Calculation (Press)**
```python
base_defect = 0.3%

# Dryness penalty: Too dry causes crumbling
if moisture < 1.5%:
    dryness_penalty = (1.5 - moisture) * 3.0
else:
    dryness_penalty = 0

# Vibration penalty: High vibration makes things worse
vibration_penalty = max(0, (vibration_hz - 75.0) * 0.05)

defect_rate = base_defect + dryness_penalty + vibration_penalty
```

---

## 🚀 Getting Started

### **Prerequisites**
- Python 3.8+
- MQTT Broker (Mosquitto): `sudo apt install mosquitto mosquitto-clients`
- OpenAI API key (for master_agent.py)
- Dependencies:
  ```bash
  pip install paho-mqtt openai
  ```

### **Start the Simulation**

**Terminal 1: Start MQTT Broker**
```bash
mosquitto -v
```

**Terminal 2: Start Monitor (real-time view)**
```bash
python monitor.py
```

**Terminal 3: Start All Machines**
```bash
# In PowerShell or terminal with multiple tabs:
python machine1_dispenser.py
python machine2_granulator.py
python machine3_dryer.py
python machine4_press.py
python machine5_qc.py
```

**Terminal 4: Start Master AI Agent**
```bash
python master_agent.py
```

### **Expected Output**

Monitor will display real-time updates:
```
[14:23:45] M1 Dispenser: Hopper=95.0kg, Buffer=5.0kg, Status=DISPENSING
[14:23:46] → M1 has powder ready (5.0kg)
[14:23:48] M2 Granulator: Input=4.75kg, Output=0.0kg, Temp=62.3°C
[14:23:50] → M2 has granules ready (4.75kg)
[14:23:52] M3 Dryer: Heat=45°C→85°C, Moisture=7.3%
[14:23:54] → M3 has dried granules ready (Moisture: 1.2%)
[14:23:56] M4 Press: RPM=1000, Vibration=75.0Hz, Defect=0.45%
[14:23:58] → M4 has pills ready (950 pills, Defect: 0.45%)
[14:24:00] M5 QC: Output=45 pills, Coating=49.8L, Defect=0.31%
[14:24:02] ✓ BATCH COMPLETE: BATCH_001 - 950 pills (Defect: 0.31%)
```

---

## 🔍 Optimization Scenarios

### **Scenario 1: High Defect Rate from Dry Granules**
- **Problem**: Dryer heat is too high → moisture too low
- **Effect**: Press produces crumbly pills
- **Solution**: AI reduces Dryer temperature to increase moisture

### **Scenario 2: Vibration Causing Crumbling**
- **Problem**: Press RPM too high → high vibration + any dryness = defects
- **Effect**: Pills crumble, QC rejects more
- **Solution**: AI reduces Press RPM to lower vibration

### **Scenario 3: Insufficient Binding**
- **Problem**: Granules too wet (dryer too cool)
- **Effect**: Pills don't bind properly
- **Solution**: AI increases Dryer temperature slightly

---

## 📊 Key Metrics to Monitor

| Metric | Good Range | Warning | Critical |
|--------|-----------|---------|----------|
| **Hopper Level** | 80-100% | 20-80% | <20% |
| **Buffer Levels** | 5-20 kg | 0-5 kg | Empty |
| **Dryer Moisture** | 1.0-2.0% | 0.5-1.0% or 2.5-5.0% | <0.5% or >5% |
| **Press Vibration** | 70-80 Hz | 80-85 Hz | >85 Hz |
| **Defect Rate** | <1.0% | 1.0-3.0% | >3.0% |
| **QC Output Rate** | >150 pills/min | 100-150 | <100 |
| **Coating Fluid** | >30L | 10-30L | <10L |

---

## 🛠️ Troubleshooting

### **"Connection refused" on MQTT**
- Mosquitto not running. Start it with `mosquitto`

### **No material flowing between machines**
- Check MQTT connectivity
- Verify machines subscribed to correct topics
- Check machine states (should be DISPENSING, PROCESSING, etc.)

### **AI recommendations not applied**
- Check OpenAI API key in master_agent.py
- Verify internet connection for API calls
- Check for JSON parsing errors

### **Defects stuck high**
- Dryer might be too hot (too dry) or too cold (won't bind)
- Check intermediate moisture levels in monitor output
- AI optimizes every 60 seconds; may need time to adjust

---

## 📝 Files Overview

| File | Purpose |
|------|---------|
| `machine1_dispenser.py` | Powder source, manages hopper and output buffer |
| `machine2_granulator.py` | Converts powder to granules |
| `machine3_dryer.py` | **CRITICAL**: Controls moisture via heat |
| `machine4_press.py` | Makes pills, calculates defects based on physics |
| `machine5_qc.py` | Inspects, coats, and finalizes pills |
| `master_agent.py` | AI coordinator, workflow management, optimization |
| `monitor.py` | Real-time display of factory floor activity |

---

## 🎓 Learning Objectives

This simulation demonstrates:
1. **Real Manufacturing**: Material flow, buffers, bottlenecks
2. **Physics Coupling**: How parameters in one machine affect downstream quality
3. **AI Optimization**: Using LLMs to make decisions in complex systems
4. **Event-Driven Architecture**: Pub/Sub communication patterns
5. **Batch Processing**: Managing work through a pipeline
6. **Quality Metrics**: Tracking and improving production defects

---

## 🚧 Future Enhancements

- [ ] Multi-batch parallel processing
- [ ] Machine failure simulation and recovery
- [ ] Energy consumption tracking
- [ ] Cost optimization alongside quality
- [ ] Predictive maintenance alerts
- [ ] Web dashboard for visualization
- [ ] Advanced AI models with reinforcement learning

---

**Created**: May 2026  
**Status**: Production Ready ✅
