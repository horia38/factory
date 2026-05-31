# 🚀 Quick Start Guide

## 5-Minute Setup

### Step 1: Install Requirements
```bash
# Install MQTT broker
# Windows: Download from https://mosquitto.org/download/
# Linux: sudo apt install mosquitto
# macOS: brew install mosquitto

# Install Python packages
pip install paho-mqtt openai
```

### Step 2: Configure OpenAI API Key
Edit `master_agent.py`, find this line:
```python
OPENAI_API_KEY = "sk-proj-..."
```
Replace with your actual OpenAI API key (get one at https://platform.openai.com/api-keys)

### Step 3: Start MQTT Broker

**Windows (PowerShell):**
```powershell
# If installed via installer
"C:\Program Files\mosquitto\mosquitto.exe"

# Or if using scoop/chocolatey
mosquitto
```

**Linux/macOS:**
```bash
mosquitto
```

Should show:
```
1685892734: mosquitto version 2.x.x starting
1685892734: Using default config from /etc/mosquitto/mosquitto.conf
1685892734: Opening ipv4 listen socket on port 1883.
```

### Step 4: Start the Factory (5 Terminal Tabs)

**Tab 1 - Monitor (Real-time dashboard):**
```bash
cd c:\Users\Horia\Desktop\factory
python monitor.py
```

**Tab 2 - Machine 1:**
```bash
python machine1_dispenser.py
```

**Tab 3 - Machine 2:**
```bash
python machine2_granulator.py
```

**Tab 4 - Machine 3:**
```bash
python machine3_dryer.py
```

**Tab 5 - Machine 4:**
```bash
python machine4_press.py
```

**Tab 6 - Machine 5:**
```bash
python machine5_qc.py
```

**Tab 7 - Master Agent (After all machines are running):**
```bash
python master_agent.py
```

---

## What You'll See

### Monitor Output Example:
```
================================================================================
🏭 FACTORY FLOOR MONITORING SYSTEM
================================================================================
Listening to all factory communications...

[14:23:45] M1 Dispenser: Hopper=100.0kg, Buffer=0.0kg, Status=IDLE
[14:23:48] ✓ M1 Powder Dispenser Powered On...
[14:23:51] 📤 COMMAND: machine1 ← start_batch
[14:23:54] M1 Dispenser: Hopper=97.5kg, Buffer=2.5kg, Status=DISPENSING
[14:23:57] → M1 has powder ready (2.5kg)
[14:24:00] M2 Granulator: Input=2.4kg, Output=0.0kg, Temp=62.3°C
[14:24:03] → M2 has granules ready (2.4kg)
[14:24:06] M3 Dryer: Heat=47°C→85°C, Moisture=5.3%
[14:24:09] → M3 has dried granules ready (Moisture: 1.8%)
[14:24:12] M4 Press: RPM=1000, Vibration=75.0Hz, Defect=0.31%
[14:24:15] → M4 has pills ready (480 pills, Defect: 0.31%)
[14:24:18] M5 QC: Output=0 pills, Coating=50.0L, Defect=0.00%
[14:24:21] ✓ BATCH COMPLETE: BATCH_001 - 475 pills (Defect: 0.21%)
[14:24:24] 📈 Production metrics show stable operation...
```

### Master Agent Output:
```
============================================================
🤖 MASTER AI AGENT ONLINE - FACTORY COORDINATION SYSTEM
============================================================
Monitoring 5 production machines...
============================================================

[14:23:41] ⏳ Waiting for machines to come online... (3/5)
[14:23:46] ⏳ Waiting for machines to come online... (5/5)
[14:23:51] ============================================================
[14:23:51] 🏭 STARTING NEW BATCH: BATCH_001
[14:23:51] ============================================================
[14:23:52] Dispatched to machine1: {"action": "start_batch", "batch_id": "BATCH_001"}
...

[14:24:30] 📊 PRODUCTION METRICS (Last 3 Batches):
[14:24:30]    BATCH_001: 475 pills, 0.21% defects
[14:24:30]    BATCH_002: 480 pills, 0.18% defects
[14:24:30]    BATCH_003: 478 pills, 0.24% defects

[14:24:31] [AI ANALYSIS]: Current production is stable. Moisture is optimal...
[14:24:31] [APPLYING OPTIMIZATIONS]:
[14:24:31]    → Adjusted machine3 target_heat_c to 86 (maintain moisture levels)
[14:24:31]    → Adjusted machine4 speed_rpm to 1000 (vibration well-controlled)
```

---

## Common Commands

### Stop Everything
Press `Ctrl+C` in each terminal (Tab by tab, or close all)

### Start Fresh Batch
- Automatic: Master agent triggers every ~30 seconds when pipeline is ready
- Manual: Edit master_agent.py batch trigger logic

### Change Dryer Heat
The AI does this automatically every 60 seconds, but you can test manually:
```
In any terminal:
mosquitto_pub -h localhost -t "factory/commands/machine3" -m '{"action":"set_heat","value":90}'
```

### Change Press RPM
```
mosquitto_pub -h localhost -t "factory/commands/machine4" -m '{"action":"set_rpm","value":950}'
```

### Refill Hopper
```
mosquitto_pub -h localhost -t "factory/commands/machine1" -m '{"action":"refill"}'
```

### Refill Coating Fluid
```
mosquitto_pub -h localhost -t "factory/commands/machine5" -m '{"action":"refill_coating"}'
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ConnectionRefusedError: [Errno 10061]` | Start mosquitto broker |
| `No module named 'paho'` | `pip install paho-mqtt` |
| `No module named 'openai'` | `pip install openai` |
| `AuthenticationError` from OpenAI | Check API key in master_agent.py |
| Machines not communicating | Make sure mosquitto is running on `localhost:1883` |
| High defect rates stuck | AI optimizes every 60s, wait or adjust manually |
| No output in monitor | Check machines are publishing (not paused) |

---

## Next Steps

1. **Observe** the factory running for 5-10 minutes to see the pipeline in action
2. **Read** [README.md](README.md) for full documentation
3. **Study** [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) to understand the physics
4. **Experiment**:
   - Manually change Dryer heat and watch defects
   - Manually change Press RPM and see vibration effects
   - Run for hours and observe AI optimization trends
5. **Modify** the code to test scenarios:
   - Change physics parameters
   - Add new machines
   - Implement different optimization strategies

---

## Key Concepts (30-Second Recap)

- **Pipeline**: Powder → Granules → Dried Granules → Pills → Finished Pills
- **Buffer Flow**: Material waits in buffers between machines
- **Physics**: Dryer heat affects moisture → affects press defects
- **Optimization**: AI adjusts heat and RPM every 60s to minimize defects
- **Communication**: All via MQTT pub/sub (very lightweight, fast)
- **Metrics**: Track defect rates, throughput, buffer levels, temperatures

---

## Performance Expectations

After ~5 minutes:
- ✅ First batch should complete
- ✅ Monitor showing real-time updates
- ✅ Master agent analyzing data

After ~15 minutes:
- ✅ Multiple batches complete (~8-10)
- ✅ AI has made at least 1 optimization
- ✅ Defect rates stabilizing

After ~1 hour:
- ✅ Production averaging <0.5% defects
- ✅ AI continuously optimizing
- ✅ ~180+ pills produced per minute

---

## Tips for Best Results

1. **Let it run for 10+ minutes** before drawing conclusions
2. **Monitor the terminal output** to understand what's happening
3. **Check batch history** in Master Agent to see trends
4. **Use MQTT commands** to manually test hypothesis about physics
5. **Keep mosquitto running** in a dedicated terminal
6. **Check internet connection** - AI calls need it

---

## Production Benchmarks

| Metric | Poor | Good | Excellent |
|--------|------|------|-----------|
| Defect Rate | >2% | 0.5-1.0% | <0.3% |
| Pills/Minute | <100 | 150-180 | >180 |
| Throughput/Hour | <1000 | 1500-2000 | >2000 |
| Buffer Efficiency | <30% | 50-70% | >70% |

---

**Time to first batch complete**: ~30 seconds  
**Time to stable operation**: ~5 minutes  
**Time to see AI optimization**: ~60 seconds after master starts
