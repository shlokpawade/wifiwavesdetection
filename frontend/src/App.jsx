import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const WS_URL = API_BASE.replace('http', 'ws') + '/ws/stream'

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v))
}

function WaveChart({ points, color, title }) {
  const polyline = useMemo(() => {
    if (!points.length) return ''
    const width = 700
    const height = 180
    const min = Math.min(...points)
    const max = Math.max(...points)
    const range = Math.max(0.001, max - min)
    return points
      .map((v, i) => {
        const x = (i / Math.max(1, points.length - 1)) * width
        const y = height - ((v - min) / range) * height
        return `${x},${y}`
      })
      .join(' ')
  }, [points])

  return (
    <div className="panel chart-panel">
      <div className="panel-title">{title}</div>
      <svg viewBox="0 0 700 180" className="wave-svg">
        <polyline points={polyline} stroke={color} fill="none" strokeWidth="2.5" />
      </svg>
    </div>
  )
}

function RadarPanel({ detected, confidence }) {
  const markerTop = 20 + (1 - clamp(confidence, 0, 1)) * 48

  return (
    <div className={`panel radar-panel ${detected ? 'pulse' : ''}`}>
      <div className="panel-title">Wi‑Fi Radar</div>
      <div className="radar-stage">
        <div className="radar-scan" />
        <div className="radar-rings">
          <span />
          <span />
          <span />
          <span />
        </div>

        <div className="wifi-emitter">📶</div>
        <div className="wifi-waves-3d">
          <span />
          <span />
          <span />
        </div>

        {detected && (
          <div className="person-marker" style={{ top: `${markerTop}%` }}>
            🧍
          </div>
        )}
      </div>
      <small>Radar lock: {detected ? 'PERSON TRACKED' : 'SCANNING...'}</small>
    </div>
  )
}

function App() {
  const [status, setStatus] = useState({
    connected: false,
    source: null,
    presence_detected: false,
    presence_confidence: 0,
    heartbeat_bpm: null,
    heartbeat_quality: 0,
    packet_rate_hz: 0,
    dropped_packets: 0,
    presence_variance_threshold: 0.02,
    calibration_mode: null,
    profiles: {},
  })
  const [raw, setRaw] = useState([])
  const [filtered, setFiltered] = useState([])
  const [variance, setVariance] = useState(0)

  const post = async (path, body = undefined, method = 'POST') => {
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) return
    setStatus(await res.json())
  }

  useEffect(() => {
    const bootstrap = async () => {
      const res = await fetch(`${API_BASE}/api/status`)
      if (!res.ok) return
      setStatus(await res.json())
    }
    void bootstrap()

    const ws = new WebSocket(WS_URL)
    ws.onopen = () => ws.send('ready')
    ws.onmessage = (event) => {
      const packet = JSON.parse(event.data)
      const { event: eventName, payload } = packet
      if (eventName === 'waves.raw') setRaw(payload.points.slice(-220))
      if (eventName === 'waves.filtered') setFiltered(payload.points.slice(-220))
      if (eventName === 'presence.state') {
        setStatus((current) => ({
          ...current,
          presence_detected: payload.detected,
          presence_confidence: payload.confidence,
          presence_variance_threshold: payload.threshold,
        }))
        setVariance(payload.variance)
      }
      if (eventName === 'heartbeat.bpm') {
        setStatus((current) => ({
          ...current,
          heartbeat_bpm: payload.bpm,
          heartbeat_quality: payload.quality,
        }))
      }
      if (eventName === 'device.health') {
        setStatus((current) => ({
          ...current,
          connected: payload.connected,
          source: payload.source,
          packet_rate_hz: payload.packetRateHz,
          dropped_packets: payload.droppedPackets,
        }))
      }
    }

    return () => ws.close()
  }, [])

  const confidencePercent = Math.round(clamp(status.presence_confidence, 0, 1) * 100)
  const qualityPercent = Math.round(clamp(status.heartbeat_quality, 0, 1) * 100)

  return (
    <div className="app-root">
      <div className="neon-bg" />
      <header>
        <h1>⚡ WiFi Waves Detection Lab</h1>
        <p>Realtime room presence + heartbeat extraction from Wi-Fi wave patterns</p>
      </header>

      <section className="metrics-grid">
        <div className={`panel metric ${status.presence_detected ? 'pulse' : ''}`}>
          <div className="panel-title">Person Detection</div>
          <div className="value">{status.presence_detected ? 'PERSON DETECTED' : 'ROOM EMPTY'}</div>
          <small>Confidence: {confidencePercent}%</small>
          <small>Variance: {variance.toFixed(4)}</small>
        </div>

        <div className="panel metric">
          <div className="panel-title">Heartbeat</div>
          <div className="value">{status.heartbeat_bpm ? `${status.heartbeat_bpm} BPM` : '—'}</div>
          <small>Signal quality: {qualityPercent}%</small>
        </div>

        <div className="panel metric">
          <div className="panel-title">Device Health</div>
          <div className="value">{status.connected ? 'CONNECTED' : 'DISCONNECTED'}</div>
          <small>Source: {status.source ?? 'none'}</small>
          <small>Packet rate: {status.packet_rate_hz.toFixed(2)} Hz</small>
        </div>
      </section>

      <section className="charts-grid">
        <WaveChart points={raw} color="#00f7ff" title="Raw Wi-Fi Waves" />
        <WaveChart points={filtered} color="#ff4be2" title="Filtered Waves" />
        <RadarPanel detected={status.presence_detected} confidence={status.presence_confidence} />
      </section>

      <section className="panel controls">
        <div className="panel-title">Controls</div>
        <div className="controls-row">
          <button onClick={() => post('/api/device/connect', { source: 'simulator' })}>Start Stream</button>
          <button className="alt" onClick={() => post('/api/device/disconnect')}>Stop Stream</button>
          <button onClick={() => post('/api/calibration/start', { mode: 'empty' })}>Calibrate Empty</button>
          <button onClick={() => post('/api/calibration/start', { mode: 'occupied' })}>Calibrate Occupied</button>
          <button className="alt" onClick={() => post('/api/calibration/stop')}>Finish Calibration</button>
        </div>
      </section>
    </div>
  )
}

export default App
