import React, { useState, useEffect } from 'react'
import axios from 'axios'

interface Location {
  id: number
  label: string
  lat: number | null
  lon: number | null
  scan_count: number
  has_wifi: boolean
  has_ble: boolean
  has_cell: boolean
  first_seen: string
  last_seen: string
}

interface Agent {
  agent_id: string
  location: string
  confidence: number
  lat: number | null
  lon: number | null
  method: string | null
  radio: string | null
  last_seen: string
}

interface Stats {
  known_locations: number
  total_scans: number
  total_agents: number
  total_fingerprints: number
}

const API_BASE = '/api'

function App() {
  const [locations, setLocations] = useState<Location[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [locRes, agentRes, statsRes] = await Promise.all([
          axios.get(`${API_BASE}/locations`),
          axios.get(`${API_BASE}/agents`),
          axios.get(`${API_BASE}/stats`),
        ])
        setLocations(locRes.data)
        setAgents(agentRes.data)
        setStats(statsRes.data)
      } catch (err) {
        setError('Failed to fetch data. Is the backend running?')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>
  if (error) return <div className="flex items-center justify-center h-screen text-red-400">{error}</div>

  return (
    <div className="min-h-screen p-6">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-blue-400">Signal Map Dashboard</h1>
        <p className="text-gray-400">Real-time location mapping for agents and IoT devices</p>
      </header>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Known Locations" value={stats.known_locations} />
          <StatCard label="Total Scans" value={stats.total_scans} />
          <StatCard label="Registered Agents" value={stats.total_agents} />
          <StatCard label="Fingerprints" value={stats.total_fingerprints} />
        </div>
      )}

      {/* Agents */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-4 text-green-400">Agents</h2>
        <div className="grid gap-3">
          {agents.map((agent) => (
            <div key={agent.agent_id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-center">
              <div>
                <span className="font-mono text-sm text-blue-300">{agent.agent_id}</span>
                <span className="ml-3 text-gray-300">{agent.location}</span>
              </div>
              <div className="text-right">
                <span className="text-sm text-gray-400">{(agent.confidence * 100).toFixed(0)}%</span>
                <span className="ml-2 text-xs text-gray-500">{agent.method}</span>
                {agent.lat && <span className="ml-2 text-xs text-gray-500">{agent.lat.toFixed(4)}, {agent.lon?.toFixed(4)}</span>}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Locations */}
      <section>
        <h2 className="text-xl font-semibold mb-4 text-purple-400">Locations ({locations.length})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-400 border-b border-gray-700">
                <th className="py-2 px-3">Label</th>
                <th className="py-2 px-3">Coordinates</th>
                <th className="py-2 px-3">Scans</th>
                <th className="py-2 px-3">Radios</th>
                <th className="py-2 px-3">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {locations.map((loc) => (
                <tr key={loc.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="py-2 px-3 font-mono text-xs">{loc.label}</td>
                  <td className="py-2 px-3 text-xs">
                    {loc.lat ? `${loc.lat.toFixed(4)}, ${loc.lon?.toFixed(4)}` : '—'}
                  </td>
                  <td className="py-2 px-3">{loc.scan_count}</td>
                  <td className="py-2 px-3">
                    {loc.has_wifi && <span className="text-blue-400 mr-1">W</span>}
                    {loc.has_ble && <span className="text-green-400 mr-1">B</span>}
                    {loc.has_cell && <span className="text-yellow-400 mr-1">C</span>}
                  </td>
                  <td className="py-2 px-3 text-xs text-gray-500">
                    {new Date(loc.last_seen).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 text-center">
      <div className="text-2xl font-bold text-white">{value.toLocaleString()}</div>
      <div className="text-sm text-gray-400">{label}</div>
    </div>
  )
}

export default App
