import React, { useState, useEffect, useRef } from 'react';
import './index.css';

const ControlCard = ({ id, machineId, title, label, action, needsValue, sendCommand }) => {
  const [val, setVal] = useState('');
  const [status, setStatus] = useState('');

  const handleSend = () => {
    sendCommand(machineId, action, needsValue ? val : undefined);
    setVal('');
    setStatus('Sent!');
    setTimeout(() => setStatus(''), 2000);
  };

  return (
    <div id={id} className="machine-box normal control-card">
      <div className="machine-title">{title}</div>
      <div className="control-group">
        {needsValue ? (
          <input 
            type="text" 
            placeholder={`Enter ${label}`} 
            value={val} 
            onChange={e => setVal(e.target.value)}
            className="control-input"
          />
        ) : (
          <div className="control-label">{label}</div>
        )}
        <button onClick={handleSend} className="control-btn">Send</button>
      </div>
      {status && <div className="control-status">{status}</div>}
    </div>
  );
};

function ControlPanel({ state, wsRef }) {
  const sendCommand = (machineId, action, valueStr) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    
    const payload = { action };
    if (valueStr !== undefined) {
      const val = parseFloat(valueStr);
      if (isNaN(val)) return;
      payload.value = val;
    }
    
    wsRef.current.send(JSON.stringify({
      topic: `factory/commands/${machineId}`,
      payload
    }));
  };

  return (
    <div className="factory-container">
      <div className="machines-grid">
        <ControlCard id="m1" machineId="machine1" title="Powder Dispenser" label="Refill Powder" action="refill" needsValue={false} sendCommand={sendCommand} />
        <ControlCard id="m2" machineId="machine2" title="Granulator" label="Speed (RPM)" action="processing_speed_rpm" needsValue={true} sendCommand={sendCommand} />
        <ControlCard id="m3" machineId="machine3" title="Dryer" label="Heat (°C)" action="target_heat_c" needsValue={true} sendCommand={sendCommand} />
        <ControlCard id="m4" machineId="machine4" title="Pill Press" label="Speed (RPM)" action="speed_rpm" needsValue={true} sendCommand={sendCommand} />
        <ControlCard id="m5" machineId="machine5" title="QC Coater" label="Refill Coating" action="refill_coating" needsValue={false} sendCommand={sendCommand} />
      </div>
    </div>
  );
}

export default function FactoryDashboard() {
  const [state, setState] = useState({
    machine1: {}, machine2: {}, machine3: {}, machine4: {}, machine5: {}, alerts: []
  });
  const [aiGlows, setAiGlows] = useState({});
  const [autoScrollPaused, setAutoScrollPaused] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    let ws;
    const connect = () => {
      ws = new WebSocket('ws://localhost:8080');
      wsRef.current = ws;
      ws.onmessage = (event) => {
        try { setState(JSON.parse(event.data)); } catch (e) {}
      };
      ws.onclose = () => setTimeout(connect, 2000);
    };
    connect();
    return () => { if (ws) ws.close(); };
  }, []);

  const isM1Starved = state.machine1.hopper_level_kg < 20;
  const isM2Overheating = state.machine2.motor_temp_c > 70;
  const isM2ViscosityHigh = state.machine2.viscosity_cp > 400;
  const isM3Overbaking = state.machine3.output_moisture_pct < 1.0;
  const isM4Jamming = state.machine4.speed_rpm < 500;
  const isM4HighDefects = state.machine4.defect_rate_pct > 5.0;

  useEffect(() => {
    const now = Date.now() / 1000;
    const newGlows = {};
    let changed = false;

    (state.alerts || []).forEach(a => {
      if (a.topic.startsWith('factory/commands/')) {
        let machineId = a.topic.split('/').pop();
        // Convert 'machine2' to 'm2'
        if (machineId.startsWith('machine')) {
          machineId = 'm' + machineId.replace('machine', '');
        }
        
        if (now - a.timestamp < 3.0) {
          newGlows[machineId] = true;
          changed = true;
        }
      }
    });

    setAiGlows(newGlows);
    
    // Automatically clear glows after 3 seconds by forcing a re-evaluation
    const timer = setTimeout(() => {
      setAiGlows(prev => ({ ...prev }));
    }, 3000);
    return () => clearTimeout(timer);
  }, [state.alerts]);

  const chatMessagesRef = useRef(null);
  const scrollTimeoutRef = useRef(null);
  
  // Track manual scrolling to pause auto-scroll
  const handleScroll = () => {
    if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
    
    const el = chatMessagesRef.current;
    if (el) {
       const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
       setAutoScrollPaused(!isAtBottom);
    }
    
    // Set a 30 second timer. If no scroll events happen for 30s, force scroll to bottom.
    scrollTimeoutRef.current = setTimeout(() => {
      setAutoScrollPaused(false);
      const el2 = chatMessagesRef.current;
      if (el2) {
        el2.scrollTop = el2.scrollHeight;
      }
    }, 30000);
  };

  // Smart auto-scroll: only scroll if not paused
  useEffect(() => {
    const el = chatMessagesRef.current;
    if (!el) return;
    
    if (!autoScrollPaused) {
      el.scrollTop = el.scrollHeight;
    }
  }, [state.alerts, autoScrollPaused]);

  const getAlertStatus = (m) => {
    if (aiGlows[m]) return 'ai-command';
    if (m === 'm1') return isM1Starved ? 'danger' : 'normal';
    if (m === 'm2') return (isM2Overheating || isM2ViscosityHigh) ? 'danger' : 'normal';
    if (m === 'm3') return isM3Overbaking ? 'danger' : 'normal';
    if (m === 'm4') return isM4HighDefects ? 'danger' : isM4Jamming ? 'warning' : 'normal';
    if (m === 'm5') return (state.machine5.actual_defect_rate_pct > 5.0) ? 'danger' : 'normal';
    return 'normal';
  };

  const m1Flow = state.machine1.status === "DISPENSING" || state.machine1.status === "PROCESSING";
  const m2Flow = state.machine2.status === "PROCESSING" || state.machine2.status === "GRANULATING";
  const m3Flow = state.machine3.status === "DRYING";
  const m4Flow = state.machine4.status === "PRESSING";

  const MachineBox = ({ id, title, stats, alertStatus }) => (
    <div className={`machine-box ${alertStatus}`} id={id}>
      <div className="machine-title">{title}</div>
      <div className="machine-stats">
        {stats.map((s, i) => (
          <div key={i} className="stat-row">
            <span className="stat-label">{s.label}:</span>
            <span className="stat-value">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );

  const path = window.location.pathname;
  if (path === '/controlpanel') {
    return <ControlPanel state={state} wsRef={wsRef} />;
  }

  return (
    <div className="factory-container">
      
      {/* Left Side: Machines Grid */}
      <div className="machines-grid">
        <svg className="svg-layer">
          <line x1="330" y1="130" x2="650" y2="130" className={`flow-line ${m1Flow ? 'active' : ''}`} />
          <line x1="790" y1="210" x2="790" y2="350" className={`flow-line ${m2Flow ? 'active' : ''}`} />
          <line x1="650" y1="430" x2="330" y2="430" className={`flow-line ${m3Flow ? 'active' : ''}`} />
          <line x1="190" y1="510" x2="190" y2="650" className={`flow-line ${m4Flow ? 'active' : ''}`} />
        </svg>

        <MachineBox 
          id="m1" title="Powder Dispenser" alertStatus={getAlertStatus('m1')}
          stats={[
            {label: 'HOPPER', value: `${state.machine1.hopper_level_kg?.toFixed(1) || '0.0'} kg`},
            {label: 'STATUS', value: state.machine1.status || 'OFFLINE'}
          ]} 
        />
        <MachineBox 
          id="m2" title="Granulator" alertStatus={getAlertStatus('m2')}
          stats={[
            {label: 'SPEED', value: `${state.machine2.processing_speed_rpm || '0'} RPM`},
            {label: 'TEMP', value: `${state.machine2.motor_temp_c?.toFixed(1) || '0.0'} °C`},
            {label: 'VISC', value: `${state.machine2.viscosity_cp?.toFixed(1) || '0.0'} cP`}
          ]} 
        />
        <MachineBox 
          id="m3" title="Dryer" alertStatus={getAlertStatus('m3')}
          stats={[
            {label: 'HEAT', value: `${state.machine3.current_heat_c?.toFixed(1) || '0.0'} °C`},
            {label: 'MOISTURE', value: `${state.machine3.output_moisture_pct?.toFixed(1) || '0.0'} %`},
            {label: 'BUFFER', value: `${state.machine3.input_buffer_kg?.toFixed(1) || '0.0'} kg`}
          ]} 
        />
        <MachineBox 
          id="m4" title="Pill Press" alertStatus={getAlertStatus('m4')}
          stats={[
            {label: 'SPEED', value: `${state.machine4.speed_rpm || '0'} RPM`},
            {label: 'VIBE', value: `${state.machine4.vibration_hz?.toFixed(1) || '0.0'} Hz`},
            {
              label: 'MOISTURE', 
              value: (
                <span style={{ color: (state.machine4.input_moisture_pct < 1.0 || state.machine4.input_moisture_pct > 3.0) ? '#ef4444' : 'inherit' }}>
                  {`${state.machine4.input_moisture_pct?.toFixed(1) || '0.0'} %`}
                </span>
              )
            }
          ]} 
        />
        <MachineBox 
          id="m5" title="QC Coater" alertStatus={getAlertStatus('m5')}
          stats={[
            {label: 'YIELD', value: `${(100 - (state.machine5.actual_defect_rate_pct || 0)).toFixed(1)} %`},
            {label: 'DEFECTS', value: `${state.machine5.actual_defect_rate_pct?.toFixed(1) || '0.0'} %`},
            {label: 'FLUID', value: `${state.machine5.coating_fluid_liters?.toFixed(1) || '0.0'} L`}
          ]} 
        />

        <div className="legend">
          <span className="legend-item"><span className="dot normal"></span> Normal</span>
          <span className="legend-item"><span className="dot danger"></span> Critical Threshold</span>
          <span className="legend-item"><span className="dot flow"></span> Material Flow</span>
        </div>
      </div>

      {/* Right Side: Chat Box */}
      <div className="chat-box">
        <div className="chat-header">Master Agent Comm Link</div>
        <div className="chat-messages" ref={chatMessagesRef} onScroll={handleScroll}>
          {(state.alerts || []).filter(a => a.topic.includes('master_agent') || a.topic.includes('events/batch_') || a.topic.includes('commands/')).map((msg, idx) => {
              const isCmd = msg.topic.includes('commands/');
              let displayMsg = '';
              if (isCmd) {
                displayMsg = `Setting ${msg.payload.action} to ${msg.payload.value}`;
              } else {
                displayMsg = msg.payload.message || JSON.stringify(msg.payload);
              }
              
              const timeStr = new Date(msg.timestamp * 1000).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
              
              return (
                <div key={idx} className={`chat-msg new-msg-flash ${isCmd ? 'cmd-msg' : ''}`} style={{animationDelay: '0s'}}>
                  <span className="chat-time">[{timeStr}]</span>
                  <span className="chat-sender">{isCmd ? `[AI -> ${msg.topic.split('/').pop().toUpperCase()}]` : '[AI]'}</span> 
                  {displayMsg}
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
