# 🏗️ Factory Simulation - Technical Architecture

## System Design

### **Communication Architecture**

```
┌─────────────────────────────────────────────────────────┐
│              MQTT Message Broker (localhost:1883)        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Pub/Sub Topics:                                         │
│  ├─ factory/status/#      (Machine status broadcasts)   │
│  ├─ factory/commands/#    (Master → Machines)           │
│  ├─ factory/events/#      (Material flow events)         │
│  └─ factory/alerts/#      (Critical alerts)            │
│                                                           │
└─────────────────────────────────────────────────────────┘
         ▲                                      ▲
         │                                      │
    ┌────┴─────┬──────────┬──────────┬──────────┴────┐
    │           │          │          │               │
[Machine1]  [Machine2]  [Machine3]  [Machine4]  [Machine5]
 Dispenser  Granulator   Dryer      Press        QC
    │           │          │          │               │
    └───────────┴──────────┴──────────┴───────────────┘
         Listens & Publishes
    
    ┌──────────────────────┬─────────────────────┐
    │                      │                     │
[MasterAgent]        [Monitor]            [Other Listeners]
 (Coordinator)     (Real-time View)
```

---

## State Management

### **Machine State Structure**

Each machine maintains a JSON state object with:

```python
{
    "machine_id": "string",           # Unique identifier
    "status": "string",               # Operational state
    "input_buffer_*": float,          # Material from upstream
    "output_buffer_*": float,         # Material to downstream
    "input_buffer_capacity_*": float, # Queue limits
    "output_buffer_capacity_*": float,
    
    # Machine-specific parameters
    "parameter_1": float,
    "parameter_2": float,
    
    # Metrics
    "cycles_completed": int,
    "total_processed": float
}
```

---

## Data Flow Through Pipeline

### **Example: One Cycle of Material Flow**

```
Time T=0s: BATCH_001 Started
├─ Master sends "start_batch" to M1, M2, M3, M4, M5 (sequential)

Time T=3s: First Update Cycle
├─ M1 Status: hopper=97.5kg, output_buffer=2.5kg (dispensing at 2.5kg/cycle)
├─ M2 Status: input_buffer=0kg, output_buffer=0kg (waiting)
├─ M3 Status: heat ramping 25°C → target 85°C
├─ M4 Status: idle (waiting for input)
├─ M5 Status: idle (waiting for input)

Time T=6s: Powder Ready Event
├─ M1 publishes: "factory/events/machine1_powder_ready"
│  └─ Payload: {"batch_id": "BATCH_001", "amount_kg": 2.5}
│
├─ M2 hears event, transfers powder to input_buffer
└─ M1's output_buffer decremented (material consumed)

Time T=9s: Granulation Complete
├─ M2 publishes: "factory/events/machine2_granules_ready"
│  └─ Payload: {"batch_id": "BATCH_001", "amount_kg": 2.4}
│
├─ M3 receives granules, starts drying process
└─ M2's output_buffer decremented

Time T=12s: Drying Complete
├─ M3 publishes: "factory/events/machine3_granules_dried"
│  └─ Payload: {
│      "batch_id": "BATCH_001",
│      "amount_kg": 2.4,
│      "moisture_pct": 1.2  ◄── CRITICAL FOR M4
│    }
│
├─ M4 receives dried granules (moisture info)
└─ This moisture value affects M4's defect calculation!

Time T=15s: Pressing Complete
├─ M4 publishes: "factory/events/machine4_pills_ready"
│  └─ Payload: {
│      "batch_id": "BATCH_001",
│      "pill_count": 480,
│      "defect_rate_pct": 0.45  ◄── QUALITY METRIC
│    }
│
└─ M5 receives pills for inspection/coating

Time T=18s: QC Complete
├─ M5 publishes: "factory/events/batch_completed"
│  └─ Payload: {
│      "batch_id": "BATCH_001",
│      "total_pills": 475,  (5 rejected)
│      "defect_rate_pct": 0.21
│    }
│
└─ MasterAgent logs batch and plans next batch

Time T=30s+: NEXT BATCH TRIGGERED
└─ Process repeats...
```

---

## Physics Model

### **1. Temperature Dynamics (Dryer)**

```
Ramp Speed: ±1-2°C per cycle
Target adjustment: Master sends "set_heat" command

Pseudo-code:
    current_heat += 2.0 if current < target
    current_heat -= 1.0 if current > target
    
    When at target:
        Holds steady ±0.1°C
```

### **2. Moisture Content (Dryer) - CRITICAL**

```
Physics Equation:
    base_moisture = 10.0 - (current_heat_c - 25.0) * 0.15
    
    Curve Example:
    ┌─────────────────────────────────┐
    │ Temperature vs Moisture Output  │
    │                                 │
    │ 100°C → 0.5% moisture (too dry) │
    │  85°C → 1.0% moisture (ideal)   │
    │  60°C → 3.25% moisture (wet)    │
    │  25°C → 10.0% moisture (soaked) │
    └─────────────────────────────────┘
    
Safe Range: 1.0-2.0% moisture
Danger: < 0.5% (crumbly) or > 5.0% (unbinds)
```

### **3. Vibration from Press Speed**

```
Physics Equation:
    base_vibration = (speed_rpm / 1000) * 75.0
    vibration = base_vibration + random(-3, +3)
    
    Examples:
    ┌────────────┬──────────┐
    │ Speed RPM  │ Vib (Hz) │
    ├────────────┼──────────┤
    │  800 RPM   │  60 Hz   │
    │ 1000 RPM   │  75 Hz   │
    │ 1200 RPM   │  90 Hz   │
    │ 1500 RPM   │ 112 Hz   │
    └────────────┴──────────┘
    
Safe Range: 70-80 Hz
Danger: > 85 Hz (pills crumble)
```

### **4. Defect Rate Calculation (Press) - THE CORE ISSUE**

```
FORMULA:
    defect_rate_pct = base_defect 
                    + dryness_penalty 
                    + vibration_penalty

COMPONENTS:

1) Base Defect: 0.3% (normal operation)

2) Dryness Penalty:
   if input_moisture < 1.5%:
       dryness_penalty = (1.5 - input_moisture) * 3.0
   else:
       dryness_penalty = 0
   
   Examples:
   ├─ 1.5% moisture → 0% penalty
   ├─ 1.0% moisture → 1.5% penalty ◄── Problems start
   ├─ 0.5% moisture → 3.0% penalty ◄── Severe crumbling
   └─ 0.1% moisture → 4.2% penalty ◄── CRITICAL

3) Vibration Penalty:
   vibration_penalty = max(0, (vibration_hz - 75.0) * 0.05)
   
   Examples:
   ├─ 75 Hz → 0% penalty (baseline)
   ├─ 80 Hz → 0.25% penalty
   ├─ 85 Hz → 0.5% penalty ◄── Getting bad
   └─ 90 Hz → 0.75% penalty ◄── Expensive

COMBINED WORST CASE:
    Too dry (0.5%) + High vibration (90 Hz):
    0.3 + 3.0 + 0.75 = 4.05% defects ◄── UNACCEPTABLE
    
    Good conditions (1.5% moisture) + Moderate vibration (75 Hz):
    0.3 + 0 + 0 = 0.3% defects ◄── EXCELLENT
```

---

## AI Optimization Loop

### **Decision Cycle**

```
                   Master Agent Main Loop
                            │
                            ▼
                  ┌──────────────────┐
                  │ Check all machines│
                  │   online? (5/5)  │
                  └────────┬─────────┘
                           │
                    Yes?───┴───No?
                    │         │
                    ▼         └──→ Wait 5s
            ┌──────────────┐
            │ Batch started?
            └────┬─────────┘
                 │
          No?────┴──→ START NEW BATCH
          │       (triggers M1→M2→M3→M4→M5)
          │
          Yes?
          │
          ▼
    ┌─────────────┐
    │Every ~60s?  │
    └──┬──────┬───┘
       │      │
       │      No: Continue monitoring
       │
       Yes: OPTIMIZATION CYCLE
       │
       ▼
    ┌──────────────────────┐
    │ Collect State:       │
    │ • All 5 machines     │
    │ • Last 5 batches    │
    │ • Metrics            │
    └───────┬──────────────┘
            │
            ▼
    ┌──────────────────────┐
    │ Call OpenAI with:    │
    │ • Current factory   │
    │   state JSON        │
    │ • Physics rules     │
    │ • Batch history    │
    └───────┬──────────────┘
            │
            ▼
    ┌──────────────────────┐
    │ Parse AI Response:   │
    │ • Analysis          │
    │ • Recommendations   │
    │  (2-3 changes)      │
    └───────┬──────────────┘
            │
            ▼
    ┌──────────────────────┐
    │ For each rec:        │
    │ • Set heat: M3      │
    │ • Set RPM: M4       │
    └───────┬──────────────┘
            │
            ▼
    ┌──────────────────────┐
    │ Wait 20s for         │
    │ changes to take      │
    │ effect              │
    └───────┬──────────────┘
            │
            └──→ Resume monitoring...
```

---

## Event-Driven Architecture

### **Machine Lifecycle**

```
STATE MACHINE:

    ┌─────────────────────────────────────────┐
    │ Machine Initialization                  │
    │ • Connect to MQTT                       │
    │ • Subscribe to commands & relevant      │
    │   events from upstream                  │
    │ • Initialize state JSON                 │
    └────────────┬────────────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────────────┐
    │ IDLE State                              │
    │ • Waiting for command                   │
    │ • Buffers empty                         │
    │ • Monitoring for upstream events       │
    └────────┬──────────────────┬─────────────┘
             │                  │
      Command?                  │ Upstream event?
             │                  │
             ▼                  ▼
    ┌──────────────┐   ┌─────────────────┐
    │ start_batch  │   │ Material arrival│
    │ Action: move │   │ (e.g., from M1) │
    │ to next state│   │ Action: fill    │
    └──────┬───────┘   │ input buffer    │
           │           └────────┬────────┘
           ▼                    │
    ┌─────────────────────────┐ │
    │ PROCESSING State        │ │
    │ • Consume input         │ │
    │ • Process material      │ │
    │ • Update physics        │ │
    │ • Produce output        │ │
    │ • Publish "_ready"      │ │
    │   events downstream     │─┘
    │ • Check if done         │
    └──┬──────────┬───────────┘
       │          │
    No input?  Complete?
       │          │
       ▼          ▼
    WAITING   Signal
    INPUT     downstream
       │       & master
       └─→ (awaiting next input or batch end)
```

---

## Quality Metrics

### **Defect Rate Tracking**

```
Pipeline Defect Points:

M4 Press Output Defects:
    • Dry material + vibration = crumbling
    • Calculated in real-time per cycle
    • Attached to every batch

M5 QC Detection:
    • Inspection phase: Detects ~70-100% of actual defects
    • Some defective pills still pass
    • Final defect rate = pills_rejected / pills_inspected

Master Agent Metrics:
    • Tracks actual defect rates per batch
    • Calculates 5-batch rolling average
    • Uses in next optimization decision
```

### **Production Efficiency**

```
Throughput Calculation:

Total Cycle Time ≈ 20-30 seconds per batch:
    • M1 dispensing: 5s
    • M2 granulation: 5s
    • M3 drying: 5s
    • M4 pressing: 3s
    • M5 QC: 2s
    
Plus buffer time for MQTT messaging and ramps.

Optimal Production:
    • ~120-180 pills per minute
    • 10-15 batches per hour
    • ~1000-2500 pills/hour with <0.5% defects
```

---

## Failure Modes & Recovery

### **Scenario 1: Low Hopper**
```
Detection: M1 hopper < 1kg
Response: M1 publishes alert
Master: Auto-sends refill command
Result: M1 hopper restored to 100kg
```

### **Scenario 2: High Defect Rate**
```
Detection: Defect rate > 3%
Root Cause: 
    • Dryer temp too high → granules too dry
    • Press vibration too high
Response:
    • Master calls AI
    • AI recommends lower heat & lower RPM
    • Commands issued
Result: Defect rate corrects within 1-2 batches
```

### **Scenario 3: Stuck Batch**
```
Detection: Input buffer depleted, status = WAITING_INPUT > 60s
Root Cause:
    • Upstream machine paused or failed
Response:
    • Monitor alerts operator
    • Master can restart upstream machines
Result: Batch flow resumes
```

---

## JSON Message Formats

### **Status Publication**

```json
{
  "machine_id": "M1_Powder_Dispenser",
  "status": "DISPENSING",
  "hopper_level_kg": 95.0,
  "hopper_capacity_kg": 100.0,
  "output_buffer_kg": 2.5,
  "output_buffer_capacity_kg": 25.0,
  "dispense_rate_kg_per_cycle": 5.0,
  "cycles_completed": 19,
  "total_powder_dispensed_kg": 47.5
}
```

### **Event Publication**

```json
{
  "batch_id": "BATCH_001",
  "amount_kg": 2.4,
  "moisture_pct": 1.2
}
```

### **Command**

```json
{
  "action": "set_heat",
  "value": 88.0
}
```

---

## Performance Characteristics

### **Computational Complexity**

| Operation | Complexity | Frequency |
|-----------|-----------|-----------|
| Publish status | O(1) | 2/6 sec |
| Process event | O(1) | ~1/6 sec |
| Physics calculation | O(1) | Per cycle |
| AI optimization call | O(n) network | Every 60s |

### **MQTT Message Load**

```
Steady State:
• 5 machines × 1 status/6s = 5 msgs/6s
• ~3-5 event msgs/6s (varies with pipeline)
• ~0.5 command msgs/6s
• ~1-2 batch completion msgs per 30s

Total: ~10 msgs/sec (very light load)
Network: <1 Mbps typical
```

---

## Configuration Tuning

### **Machine-Level Adjustments**

```python
# Dryer
target_heat_c: 80-95°C (adjust for moisture needs)
current_heat_c: Ramps at ±1-2°C per 3s

# Press
speed_rpm: 800-1200 RPM (lower = less vibration)
vibration_hz: Calculated from speed

# QC
inspection_speed: 100 pills/min (fixed)
coating_effectiveness: 95% (quality factor)
```

### **System-Level Adjustments**

```python
# Master Agent
optimization_interval: 60s (check every N cycles)
batch_wait_threshold: Input buffer empty for 20+ cycles

# All machines
cycle_time: 3s (MQTT poll interval)
```

---

## Testing Scenarios

### **Test 1: Steady Production**
```
Goal: Baseline defect rate
Steps:
1. Start all machines
2. Run 10 batches
3. Monitor defect rate trend
Expected: Stabilizes around 0.3-0.5%
```

### **Test 2: Optimize for Low Defects**
```
Goal: AI optimization effectiveness
Steps:
1. Start simulation
2. Let AI run for 30 minutes
3. Track defect rate improvement
Expected: Reduces from ~1% → <0.5%
```

### **Test 3: Recovery from Anomaly**
```
Goal: Test self-healing
Steps:
1. Start all machines
2. Manually increase Dryer heat to 100°C
3. Observe defect spike
4. Let AI optimize
Expected: Defect rate recovers within 1-2 batches
```

---

**Document Version**: 1.0  
**Last Updated**: May 2026
