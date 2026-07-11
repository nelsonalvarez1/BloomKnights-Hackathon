// Fetch calls to the backend. Shapes match backend/schemas.py — that file is
// the contract; change it first, then update here.

// Empty string in dev keeps requests on the Vite proxy (see vite.config.js).
// In production, set VITE_API_URL to the deployed backend's URL.
const API_URL = import.meta.env.VITE_API_URL || ''

async function request(path, options) {
  const res = await fetch(`${API_URL}${path}`, options)
  if (!res.ok) throw new Error(`${path} -> ${res.status}`)
  return res.json()
}

export const fetchStores = () => request('/api/stores')

export const fetchSatellite = (storeId) =>
  request(`/api/satellite?store_id=${storeId}`)

export const fetchTrends = (storeId) =>
  request(`/api/trends?store_id=${storeId}`)

export const fetchJets = (storeId) => request(`/api/jets?store_id=${storeId}`)

export const fetchEdgar = (storeId) => request(`/api/edgar?store_id=${storeId}`)

export const generateNarrative = (storeId) =>
  request('/api/narrative', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ store_id: storeId }),
  })
