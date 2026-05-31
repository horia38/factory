# 🔍 Factory Simulation - Debugging Guide

If machines are stuck in IDLE/WAITING_INPUT after batch starts, follow these steps:

## Step 1: Test MQTT Connection

Run the connectivity test:
```bash
python test_mqtt.py
```

**Expected output:**
```
✓ Connected to broker successfully!
✓ Published successfully
✓ MQTT is working correctly!
```

**If it fails:** 
- Make sure mosquitto is running in its own terminal
- Windows: `mosquitto.exe` or `"C:\Program Files\mosquitto\mosquitto.exe"`
- Linux/Mac: `mosquitto`

---

## Step 2: Check Machines Are Receiving Commands

Look at the **Machine 1 terminal** output. After you see the batch start, you should see:

```
[DEBUG M1] Received message on topic: factory/commands/machine1
[DEBUG M1] Parsed command: {'action': 'start_batch', 'batch_id': 'BATCH_001'}
[DEBUG M1] Action: start_batch
✓ [M1 COMMAND] Starting batch BATCH_001, status now: DISPENSING
```

**If you DON'T see these messages:**
- Machines aren't receiving the commands
- Problem is likely with MQTT broker or topic subscription

**If you DO see these messages:**
- Go to Step 3

---

## Step 3: Check Master Agent Is Publishing Commands

Look at the **Master Agent terminal**. After "All machines online!" you should see:

```
🏭 STARTING NEW BATCH: BATCH_001
============================================================
📤 Publishing start_batch to machine1...
📤 Publishing start_batch to machine2...
📤 Publishing start_batch to machine3...
📤 Publishing start_batch to machine4...
📤 Publishing start_batch to machine5...
✓ All batch start commands published!
```

**If you don't see this:**
- Master agent isn't reaching the `start_new_batch()` function
- Check if it's waiting for machines to come online (check previous terminal lines)

**If you see this but machines aren't responding:**
- MQTT broker is running but messages aren't being delivered
- Try restarting the broker

---

## Step 4: Manual Command Test

In a terminal, use mosquitto tools to test manually:

**Terminal 1** - Subscribe to M1 commands:
```bash
mosquitto_sub -h localhost -t "factory/commands/machine1"
```

**Terminal 2** - Send a test command:
```bash
mosquitto_pub -h localhost -t "factory/commands/machine1" -m '{"action":"start_batch","batch_id":"MANUAL_TEST"}'
```

**Expected:** The subscriber terminal should show the message appear.

If it doesn't, your MQTT broker isn't working.

---

## Step 5: Check Machine Status Publishing

All machines should publish status every 6 seconds. In monitor terminal, you should see:

```
[14:23:45] M1 Dispenser: Hopper=100.0kg, Buffer=0.0kg, Status=IDLE
[14:23:48] M2 Granulator: Input=0.0kg, Output=0.0kg, Temp=25.0°C
[14:23:51] M3 Dryer: Heat=25°C→85°C, Moisture=10.0%
```

**If status isn't changing after batch starts:**
- Machines received the command but the main loop isn't updating state
- This suggests a threading or variable scoping issue

---

## Common Issues & Solutions

### Issue: "Connection refused" error
**Solution:** 
```bash
# Windows
"C:\Program Files\mosquitto\mosquitto.exe"

# Or download from: https://mosquitto.org/download/
```

### Issue: Machines print "Powered On" but never get commands
**Solution:**
1. Check that `client.loop_start()` is called AFTER subscribe
2. Verify MQTT broker hostname is `localhost` and port is `1883`
3. Try: `mosquitto_sub -h localhost -t "factory/commands/#"` to see ALL commands

### Issue: Master says "Waiting for machines" forever
**Solution:**
- Machines need to publish status once to register
- Status publishes every 6 seconds
- Wait 30+ seconds for all 5 machines to appear
- Or check if machines are stuck with syntax errors

### Issue: See command debug output but nothing processes
**Solution:**
- Add to Machine 1 terminal to debug:
```bash
# Stop M1
# Run with explicit debugging:
python -u machine1_dispenser.py
```

The `-u` flag makes Python output unbuffered so you see messages immediately.

---

## How to Run Full Diagnostic

**Terminal A:** Broker
```bash
mosquitto
```

**Terminal B:** Monitor (watch everything)
```bash
python monitor.py
```

**Terminal C:** Test MQTT
```bash
python test_mqtt.py
```

**If test passes** → Continue to terminal D-I

**Terminal D-I:** Start all machines (one terminal each)
```bash
python machine1_dispenser.py      # Terminal D
python machine2_granulator.py     # Terminal E
python machine3_dryer.py          # Terminal F
python machine4_press.py          # Terminal G
python machine5_qc.py             # Terminal H
```

**Watch Terminal B (monitor)** - Wait for all 5 machines to show status

**Terminal I:** Master Agent
```bash
python master_agent.py
```

**Now watch for:**
1. Master prints "All machines online!"
2. Master prints "STARTING NEW BATCH"
3. Master prints "Publishing start_batch to machine1/2/3/4/5"
4. Check Terminal D (M1) for debug output showing it received the command
5. Monitor should show status changing from IDLE → DISPENSING → events flowing

---

## What the Correct Flow Looks Like

```
Master: "📤 Publishing start_batch to machine1..."
    ↓
Machine1 terminal: "[DEBUG M1] Received message on topic: factory/commands/machine1"
                   "✓ [M1 COMMAND] Starting batch..."
    ↓
Machine1 main loop: Starts dispensing
    ↓
Machine1 publishes: "factory/events/machine1_powder_ready"
    ↓
Machine2 receives event in on_message callback
Machine2 status: PROCESSING → granulates
    ↓
Machine2 publishes: "factory/events/machine2_granules_ready"
    ↓
... continues down the pipeline
```

If you're stopping at Step 1 (master not sending) or Step 2 (machines not receiving), the issue is there.

---

## Last Resort: Restart Everything

```bash
# 1. Kill all terminals with Ctrl+C
# 2. Kill broker with Ctrl+C
# 3. Wait 5 seconds
# 4. Start fresh from Step 1 in the procedure above
```

---

Let me know what debug output you see from these steps!
