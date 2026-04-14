"use client";

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { servers, clients, createPacket } from '@/utils/network';

// ── Floating particles (client-only) ──
function Particles() {
  const [items, setItems] = useState([]);
  useEffect(() => {
    setItems(Array.from({ length: 15 }, (_, i) => ({
      id: i, left: Math.random() * 100, size: 1 + Math.random() * 2,
      dur: 8 + Math.random() * 16, delay: Math.random() * 20, op: 0.2 + Math.random() * 0.4,
    })));
  }, []);
  return (
    <div className="particles">
      {items.map(p => (
        <div key={p.id} className="particle" style={{
          left: `${p.left}%`, width: `${p.size}px`, height: `${p.size}px`,
          opacity: p.op, animationDuration: `${p.dur}s`, animationDelay: `${p.delay}s`,
        }} />
      ))}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
//  Main page
// ════════════════════════════════════════════════════════════════
const MAX_CONCURRENT = 8;

export default function Home() {
  const chartRef = useRef(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [stats, setStats] = useState({ total: 0, success: 0, dropped: 0, lossRate: '0.0' });
  const [activeClientIds, setActiveClientIds] = useState(new Set());
  const [history, setHistory] = useState([]);

  // Track active line IDs (NOT React-rendered — drives chart directly)
  const activeRef = useRef(new Map()); // lineId → clientId

  // ── Load world map ──
  useEffect(() => {
    fetch('https://cdn.jsdelivr.net/npm/echarts@4.9.0/map/json/world.json')
      .then(r => r.json())
      .then(geo => { echarts.registerMap('world', geo); setMapLoaded(true); });
  }, []);

  // ── Helper: get chart instance safely ──
  const getChart = useCallback(() => {
    try {
      return chartRef.current?.getEchartsInstance();
    } catch { return null; }
  }, []);

  // ── Helper: sync active client IDs to React state ──
  const syncClientVisibility = useCallback(() => {
    const ids = new Set([...activeRef.current.values()].filter(Boolean));
    setActiveClientIds(ids);
  }, []);

  // ── Convert backend API packet → internal format ──
  const apiToInternal = useCallback((apiPkt) => {
    const fromCoord = [apiPkt.source.lng, apiPkt.source.lat];
    const toCoord   = [apiPkt.destination.lng, apiPkt.destination.lat];

    const status = apiPkt.status;
    const protocol = apiPkt.protocol;

    let endCoord = toCoord;
    let period = 3;
    if (status === 'delayed') period = 6;
    if (status === 'dropped') {
      endCoord = [
        fromCoord[0] + (toCoord[0] - fromCoord[0]) * 0.6,
        fromCoord[1] + (toCoord[1] - fromCoord[1]) * 0.6,
      ];
    }

    const color    = { success: '#00ff88', delayed: '#ffcc00', dropped: '#ff3366' }[status];
    const dotColor = { TCP: '#00d2ff', UDP: '#a855f7', ICMP: '#ffffff' }[protocol];
    const lifetime = (status === 'dropped' ? period * 0.6 : period) * 1000 + 300;

    // Find which client is involved
    const allClients = clients;
    const client = allClients.find(c =>
      c.ip === apiPkt.source.ip || c.ip === apiPkt.destination.ip
    );

    return {
      id: apiPkt.id,
      _key: `${Date.now()}_${Math.random().toString(36).slice(2,6)}`,
      from: { name: apiPkt.source.name, ip: apiPkt.source.ip, coord: fromCoord },
      to: { name: apiPkt.destination.name, ip: apiPkt.destination.ip, coord: toCoord },
      status, protocol, color, dotColor, period, lifetime,
      clientId: client ? client.id : null,
      coords: [fromCoord, endCoord],
      size: apiPkt.payloadSize,
      timestamp: apiPkt.timestamp,
    };
  }, []);

  // ── Render a packet on the map ──
  const renderPacket = useCallback((pkt) => {
    if (activeRef.current.size >= MAX_CONCURRENT) return;

    const chart = getChart();
    if (!chart) return;

    const lineId = `line_${pkt._key}`;

    // Build per-line data
    //  - lineStyle.color = status color (green/yellow/red)
    //  - effect.color    = protocol color (TCP cyan / UDP purple / ICMP white)
    const lineData = {
      coords: pkt.coords,
      lineStyle: { color: pkt.color, width: 1.5, opacity: 0.4, curveness: 0.3 },
      effect: {
        show: true, period: pkt.period, trailLength: 0.4,
        symbol: 'circle', symbolSize: 7, color: pkt.dotColor,
      },
      packetData: {
        id: pkt.id, source: pkt.from.ip, destination: pkt.to.ip,
        sourceName: pkt.from.name, destName: pkt.to.name,
        protocol: pkt.protocol, status: pkt.status,
        size: pkt.size, timestamp: pkt.timestamp,
      },
    };

    // ADD: Merge a new series (existing series untouched)
    try {
      const existing = (chart.getOption().series || []).filter(Boolean);
      chart.setOption({
        series: [
          ...existing,
          {
            id: lineId,
            type: 'lines',
            coordinateSystem: 'geo',
            zlevel: 3,
            polyline: false,
            effect: lineData.effect,
            lineStyle: lineData.lineStyle,
            data: [lineData],
          },
        ],
      });
    } catch { return; }

    activeRef.current.set(lineId, pkt.clientId);
    syncClientVisibility();

    // REMOVE: After lifetime, hide then cleanup
    setTimeout(() => {
      const c = getChart();
      if (c) {
        try {
          c.setOption({ series: [{ id: lineId, data: [], effect: { show: false } }] });
        } catch { /* chart may be gone */ }
      }
      activeRef.current.delete(lineId);
      syncClientVisibility();

      if (activeRef.current.size === 0 && c) {
        setTimeout(() => {
          try {
            const chart2 = getChart();
            if (!chart2) return;
            const opt = chart2.getOption();
            const baseSeries = (opt.series || []).filter(s => s && s.type !== 'lines');
            chart2.setOption({ series: baseSeries }, { replaceMerge: ['series'] });
          } catch { /* ignore */ }
        }, 200);
      }
    }, pkt.lifetime);

    // Stats
    setStats(prev => {
      const total = prev.total + 1;
      const success = pkt.status === 'success' ? prev.success + 1 : prev.success;
      const dropped = pkt.status === 'dropped' ? prev.dropped + 1 : prev.dropped;
      return { total, success, dropped, lossRate: ((dropped / total) * 100).toFixed(1) };
    });

    // History
    setHistory(prev => {
      const next = [...prev, { status: pkt.status }];
      return next.length > 30 ? next.slice(-30) : next;
    });
  }, [getChart, syncClientVisibility]);

  // ── Manual send (button) — uses local generator ──
  const sendPacket = useCallback(() => {
    renderPacket(createPacket());
  }, [renderPacket]);

  // ── Auto-poll backend every 1 second ──
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:4000/api/packet');
        if (!res.ok) return;
        const packets = await res.json();
        packets.forEach(apiPkt => {
          const pkt = apiToInternal(apiPkt);
          renderPacket(pkt);
        });
      } catch {
        // Backend not running — silently skip
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [apiToInternal, renderPacket]);

  // ── Lock vertical drag ──
  const handleGeoRoam = useCallback(() => {
    const inst = getChart();
    if (!inst) return;
    const opt = inst.getOption();
    if (!opt.geo?.[0]) return;
    const center = opt.geo[0].center || [0, 0];
    if (Math.abs(center[1]) > 0.01) {
      inst.setOption({ geo: { center: [center[0], 0] } });
    }
  }, [getChart]);

  // ── Derived data ──
  const serverData = servers.map(s => ({ name: s.name, value: [...s.coord, s.ip] }));
  const clientData = clients
    .filter(c => activeClientIds.has(c.id))
    .map(c => ({ name: c.name, value: [...c.coord, c.ip] }));

  // ── Base chart option (no lines — those are managed imperatively) ──
  const option = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(6,18,38,0.95)',
      borderColor: 'rgba(100,255,218,0.4)',
      borderWidth: 1,
      padding: [12, 16],
      textStyle: { color: '#ccd6f6', fontFamily: 'Inter, sans-serif', fontSize: 12 },
      extraCssText: 'backdrop-filter:blur(8px);box-shadow:0 8px 32px rgba(0,0,0,0.5);border-radius:8px;',
      formatter(params) {
        if (params.seriesType === 'lines' && params.data?.packetData) {
          const d = params.data.packetData;
          const sc = { success: '#00ff88', delayed: '#ffcc00', dropped: '#ff3366' }[d.status] || '#ccc';
          return `<div style="font-family:'JetBrains Mono',monospace;line-height:1.8;">
            <div style="color:#64ffda;font-weight:700;font-size:13px;font-family:'Orbitron',sans-serif;letter-spacing:1px;">⬡ ${d.id}</div>
            <div style="border-top:1px solid rgba(31,64,104,0.5);margin:4px 0 8px;"></div>
            <div>📍 ${d.sourceName} <span style="color:#5a6a8a;">(${d.source})</span></div>
            <div>🎯 ${d.destName} <span style="color:#5a6a8a;">(${d.destination})</span></div>
            <div>📦 Protocol: <span style="color:#00d2ff;font-weight:600;">${d.protocol}</span></div>
            <div>📊 Payload: <span style="color:#8892b0;">${d.size} B</span></div>
            <div>🚥 Status: <span style="color:${sc};font-weight:600;text-transform:uppercase;">${d.status}</span></div>
          </div>`;
        }
        return params.name;
      },
    },
    geo: {
      map: 'world', roam: 'move', zoom: 1.2, top: '25%', center: [0, 0],
      scaleLimit: { min: 1.2, max: 1.2 },
      itemStyle: {
        areaColor: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#0d1f3c' }, { offset: 1, color: '#061228' },
        ]),
        borderColor: '#1a3a5c', borderWidth: 0.8,
        shadowColor: 'rgba(100,255,218,0.1)', shadowBlur: 10,
      },
      emphasis: { disabled: true },
      silent: true,
      selectedMode: false,
    },
    series: [
      {
        id: 'servers',
        type: 'effectScatter', coordinateSystem: 'geo', zlevel: 2,
        rippleEffect: { brushType: 'stroke', scale: 5, period: 3 },
        label: { show: true, position: 'right', formatter: '{b}', color: '#64ffda', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 500 },
        symbol: 'diamond', symbolSize: 14,
        itemStyle: {
          color: new echarts.graphic.RadialGradient(0.5, 0.5, 0.5, [
            { offset: 0, color: '#64ffda' }, { offset: 1, color: '#00a67d' },
          ]),
          shadowColor: 'rgba(100,255,218,0.6)', shadowBlur: 15,
        },
        data: serverData,
      },
      {
        id: 'clients',
        type: 'effectScatter', coordinateSystem: 'geo', zlevel: 2,
        rippleEffect: { brushType: 'stroke', scale: 3, period: 4 },
        label: { show: true, position: 'right', formatter: '{b}', color: '#6a7a9a', fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
        symbolSize: 8,
        itemStyle: {
          color: new echarts.graphic.RadialGradient(0.5, 0.5, 0.5, [
            { offset: 0, color: '#00d2ff' }, { offset: 1, color: '#0080aa' },
          ]),
          shadowColor: 'rgba(0,210,255,0.4)', shadowBlur: 10,
        },
        data: clientData,
      },
    ],
  }), [serverData, clientData]);

  // ── Trend chart ──
  const trendOption = useMemo(() => {
    let sc = 0, dc = 0;
    const sd = [], dd = [];
    history.forEach(h => {
      if (h.status === 'success') sc++;
      if (h.status === 'dropped') dc++;
      sd.push(sc); dd.push(dc);
    });
    return {
      grid: { top: 5, right: 5, bottom: 5, left: 5 },
      xAxis: { type: 'category', show: false, data: history.map((_, i) => i) },
      yAxis: { type: 'value', show: false },
      series: [
        { type: 'line', data: sd, smooth: true, showSymbol: false, lineStyle: { color: '#00ff88', width: 1.5 },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0,255,136,0.25)' }, { offset: 1, color: 'rgba(0,255,136,0)' },
          ]) } },
        { type: 'line', data: dd, smooth: true, showSymbol: false, lineStyle: { color: '#ff3366', width: 1.5 },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(255,51,102,0.2)' }, { offset: 1, color: 'rgba(255,51,102,0)' },
          ]) } },
      ],
    };
  }, [history]);

  return (
    <div style={{ width: '100vw', height: '100vh', position: 'relative', overflow: 'hidden' }}>
      <div className="scene-bg" />
      <Particles />
      <div className="scanline" />

      <div className="brand-header">
        <div style={{ textAlign: 'center' }}>
          <div className="brand-title">NETSCOPE</div>
          <div className="brand-subtitle">Global Network Packet Visualizer</div>
        </div>
      </div>

      {/* Control panel — bottom left */}
      <div className="glass-panel" style={{ position: 'absolute', bottom: '20px', left: '20px', padding: '20px', zIndex: 10, width: '300px' }}>
        <div style={{ fontFamily: "'Orbitron', sans-serif", fontWeight: 700, fontSize: '11px', color: '#64ffda', letterSpacing: '3px', textTransform: 'uppercase', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#64ffda', boxShadow: '0 0 8px #64ffda', animation: 'pulse 2s ease-in-out infinite' }} />
          LIVE MONITOR
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '16px' }}>
          <div className="stat-card neutral"><div className="stat-label">Sent</div><div className="stat-value" style={{ color: '#ccd6f6' }}>{stats.total}</div></div>
          <div className="stat-card success"><div className="stat-label">OK</div><div className="stat-value" style={{ color: '#00ff88' }}>{stats.success}</div></div>
          <div className="stat-card danger"><div className="stat-label">Loss</div><div className="stat-value" style={{ color: '#ff3366' }}>{stats.lossRate}%</div></div>
        </div>

        <div style={{ background: 'rgba(10,25,50,0.4)', border: '1px solid rgba(31,64,104,0.3)', borderRadius: '6px', padding: '4px', marginBottom: '16px' }}>
          <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: '9px', color: '#5a6a8a', letterSpacing: '1px', padding: '4px 8px 0', textTransform: 'uppercase' }}>TREND (LAST 30)</div>
          <ReactECharts option={trendOption} style={{ height: '60px', width: '100%' }} opts={{ renderer: 'svg' }} />
        </div>

        <button className="send-btn" onClick={sendPacket}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
          TRANSMIT
        </button>

        <div style={{ marginTop: '16px' }}>
          <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: '9px', color: '#5a6a8a', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '8px' }}>STATUS</div>
          <div className="legend-row" style={{ marginBottom: '10px' }}>
            <span className="legend-item"><div className="legend-dot" style={{ background: '#00ff88', boxShadow: '0 0 6px #00ff88' }} />Success</span>
            <span className="legend-item"><div className="legend-dot" style={{ background: '#ffcc00', boxShadow: '0 0 6px #ffcc00' }} />Latency</span>
            <span className="legend-item"><div className="legend-dot" style={{ background: '#ff3366', boxShadow: '0 0 6px #ff3366' }} />Dropped</span>
          </div>
          <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: '9px', color: '#5a6a8a', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '8px' }}>PROTOCOL</div>
          <div className="legend-row">
            <span className="legend-item"><div className="legend-dot" style={{ background: '#00d2ff', boxShadow: '0 0 6px #00d2ff' }} />TCP</span>
            <span className="legend-item"><div className="legend-dot" style={{ background: '#a855f7', boxShadow: '0 0 6px #a855f7' }} />UDP</span>
            <span className="legend-item"><div className="legend-dot" style={{ background: '#ffffff', boxShadow: '0 0 6px #ffffff' }} />ICMP</span>
          </div>
        </div>
      </div>

      {mapLoaded && (
        <ReactECharts
          ref={chartRef}
          option={option}
          notMerge={false}
          lazyUpdate={true}
          onEvents={{ georoam: handleGeoRoam }}
          style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0, zIndex: 1 }}
        />
      )}

      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
    </div>
  );
}
