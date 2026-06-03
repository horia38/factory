import React, { useState, useEffect, useRef } from 'react';
import './index.css';

export default function FactoryDashboard() {
  const [state, setState] = useState({
    machine1: {}, machine2: {}, machine3: {}, machine4: {}, machine5: {}, alerts: []
  });
  const [aiGlows, setAiGlows] = useState({});

  useEffect(() => {
    let ws;
    const connect = () => {
      ws = new WebSocket('ws://localhost:8080');
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
  
  // Smart auto-scroll: only scroll if already near bottom
  useEffect(() => {
    const el = chatMessagesRef.current;
    if (!el) return;
    
    // Check if scrolled near bottom (within 100px)
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    
    if (isAtBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [state.alerts]);

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
            {label: 'HOPPER', value: state.machine1.hopper_level_kg?.toFixed(1) || '0.0'},
            {label: 'STATUS', value: state.machine1.status || 'OFFLINE'}
          ]} 
        />
        <MachineBox 
          id="m2" title="Granulator" alertStatus={getAlertStatus('m2')}
          stats={[
            {label: 'SPEED', value: state.machine2.processing_speed_rpm || '0.0'},
            {label: 'TEMP', value: `${state.machine2.motor_temp_c?.toFixed(1) || '0.0'}C`},
            {label: 'VISC', value: `${state.machine2.viscosity_cp?.toFixed(1) || '0.0'}cP`}
          ]} 
        />
        <MachineBox 
          id="m3" title="Dryer" alertStatus={getAlertStatus('m3')}
          stats={[
            {label: 'HEAT', value: state.machine3.current_heat_c?.toFixed(1) || '0.0'},
            {label: 'MOISTURE', value: `${state.machine3.output_moisture_pct?.toFixed(1) || '0.0'}%`},
            {label: 'BUFFER', value: state.machine3.input_buffer_kg?.toFixed(1) || '0.0'}
          ]} 
        />
        <MachineBox 
          id="m4" title="Pill Press" alertStatus={getAlertStatus('m4')}
          stats={[
            {label: 'SPEED', value: state.machine4.speed_rpm || '0.0'},
            {label: 'VIBE', value: `${state.machine4.vibration_hz?.toFixed(1) || '0.0'}Hz`},
            {label: 'MOISTURE', value: `${state.machine4.input_moisture_pct?.toFixed(1) || '0.0'}%`}
          ]} 
        />
        <MachineBox 
          id="m5" title="QC Coater" alertStatus={getAlertStatus('m5')}
          stats={[
            {label: 'YIELD', value: `${(100 - (state.machine5.actual_defect_rate_pct || 0)).toFixed(1)}%`},
            {label: 'DEFECTS', value: `${state.machine5.actual_defect_rate_pct?.toFixed(1) || '0.0'}%`},
            {label: 'FLUID', value: state.machine5.coating_fluid_liters?.toFixed(1) || '0.0'}
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
        <div className="chat-messages" ref={chatMessagesRef}>
          {(state.alerts || []).filter(a => a.topic.includes('master_agent') || a.topic.includes('events/batch_') || a.topic.includes('commands/')).map((msg, idx) => {
              const isCmd = msg.topic.includes('commands/');
              let displayMsg = '';
              if (isCmd) {
                displayMsg = `Setting ${msg.payload.action} to ${msg.payload.value}`;
              } else {
                displayMsg = msg.payload.message || JSON.stringify(msg.payload);
              }
              
              return (
                <div key={idx} className={`chat-msg new-msg-flash ${isCmd ? 'cmd-msg' : ''}`} style={{animationDelay: '0s'}}>
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
