import React, { useState } from 'react';
import axios from 'axios';
import { 
  Plane, Calendar, MapPin, Wallet, 
  Map, Activity, Navigation, Loader2, Sparkles, AlertCircle
} from 'lucide-react';
import './index.css';

function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  
  // Form State
  const [formData, setFormData] = useState({
    source_city: 'Mumbai',
    destination: 'Tokyo',
    start_date: '2026-10-10',
    end_date: '2026-10-13',
    budget: '200000 INR',
    train_class: '3A',
    rail_distance_km: '',
    passengers: 1,
    random_seed: 0,
    transport_mode: 'Flight',
    hotel_type: '4-star',
    interests: ['Food', 'Culture']
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleInterestToggle = (interest) => {
    setFormData(prev => {
      const interests = prev.interests.includes(interest)
        ? prev.interests.filter(i => i !== interest)
        : [...prev.interests, interest];
      return { ...prev, interests };
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post('http://localhost:8080/api/plan', {
        ...formData,
        rail_distance_km: formData.transport_mode === 'Train' ? Number(formData.rail_distance_km) : null,
      });
      setResult(response.data.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred while planning your trip.');
    } finally {
      setLoading(false);
    }
  };

  const allInterests = ["Food", "Adventure", "Culture", "Shopping", "Nature", "Nightlife"];

  return (
    <div className="app-container">
      <main className="main-content">
        
        {/* Sidebar / Form */}
        <aside className="glass-card" style={{ alignSelf: 'start', position: 'sticky', top: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '2rem' }}>
            <div style={{ background: 'var(--accent-gradient)', padding: '0.5rem', borderRadius: '12px' }}>
              <Plane color="white" size={24} />
            </div>
            <h2 style={{ fontSize: '1.5rem', margin: 0 }}>Voyage<span className="gradient-text">AI</span></h2>
          </div>
          
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label"><MapPin size={14} style={{ display: 'inline', marginRight: '4px' }}/> Origin</label>
              <input type="text" name="source_city" value={formData.source_city} onChange={handleChange} className="form-input" required />
            </div>
            
            <div className="form-group">
              <label className="form-label"><Navigation size={14} style={{ display: 'inline', marginRight: '4px' }}/> Destination</label>
              <input type="text" name="destination" value={formData.destination} onChange={handleChange} className="form-input" required />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label"><Calendar size={14} style={{ display: 'inline', marginRight: '4px' }}/> Start</label>
                <input type="date" name="start_date" value={formData.start_date} onChange={handleChange} className="form-input" required />
              </div>
              <div className="form-group">
                <label className="form-label"><Calendar size={14} style={{ display: 'inline', marginRight: '4px' }}/> End</label>
                <input type="date" name="end_date" value={formData.end_date} onChange={handleChange} className="form-input" required />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label"><Wallet size={14} style={{ display: 'inline', marginRight: '4px' }}/> Target Budget</label>
              <input type="text" name="budget" value={formData.budget} onChange={handleChange} className="form-input" required />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Transport</label>
                <select name="transport_mode" value={formData.transport_mode} onChange={handleChange} className="form-select">
                  <option value="Flight">Flight</option>
                  <option value="Train">Train</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Hotel Class</label>
                <select name="hotel_type" value={formData.hotel_type} onChange={handleChange} className="form-select">
                  <option value="Budget">Budget</option>
                  <option value="3-star">3-star</option>
                  <option value="4-star">4-star</option>
                  <option value="5-star">5-star</option>
                </select>
              </div>
            </div>

            {formData.transport_mode === 'Train' && <div className="form-group">
              <label className="form-label" htmlFor="rail-distance">Source to destination railway distance (km)</label>
              <input id="rail-distance" className="form-input" type="number" name="rail_distance_km" min="0.01" step="any" value={formData.rail_distance_km} onChange={handleChange} placeholder="Enter one-way distance in km" required />
              <p>This one-way distance is used for each outbound and return leg. All four classes show configured fare estimates.</p>
              <label>Train class for budget</label><select name="train_class" value={formData.train_class} onChange={handleChange}>{['SL','3A','2A','1A'].map(code => <option key={code}>{code}</option>)}</select>
            </div>}
            <div className="form-group"><label>Travelers</label><input type="number" min="1" name="passengers" value={formData.passengers} onChange={handleChange}/><label>Selection seed</label><input type="number" name="random_seed" value={formData.random_seed} onChange={handleChange}/></div>
            <div className="form-group">
              <label className="form-label">Interests</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {allInterests.map(interest => (
                  <button
                    key={interest}
                    type="button"
                    onClick={() => handleInterestToggle(interest)}
                    style={{
                      background: formData.interests.includes(interest) ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                      color: formData.interests.includes(interest) ? 'white' : 'var(--text-secondary)',
                      border: `1px solid ${formData.interests.includes(interest) ? 'var(--accent-primary)' : 'var(--border-color)'}`,
                      padding: '0.3rem 0.75rem',
                      borderRadius: '99px',
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                  >
                    {interest}
                  </button>
                ))}
              </div>
            </div>

            <button type="submit" className="btn-primary" disabled={loading} style={{ marginTop: '1.5rem' }}>
              {loading ? <Loader2 className="spinner" size={18} /> : <Sparkles size={18} />}
              {loading ? 'Formulating Journey...' : 'Plan My Journey'}
            </button>
          </form>
        </aside>

        {/* Main Content Area */}
        <section>
          {!result && !loading && !error && (
            <div className="hero">
              <h1>AI Travel <span className="gradient-text">Intelligence</span></h1>
              <p>Your enterprise-grade AI travel concierge. Fill in the details on the left to generate a professional travel blueprint utilizing live data.</p>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginTop: '4rem', textAlign: 'left' }}>
                <div className="card">
                  <Activity size={32} color="var(--accent-primary)" style={{ marginBottom: '1rem' }}/>
                  <h3 style={{ marginBottom: '0.5rem' }}>Live Data Agents</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Real-time flight and hotel data fetched instantly for accurate planning.</p>
                </div>
                <div className="card">
                  <Map size={32} color="var(--accent-primary)" style={{ marginBottom: '1rem' }}/>
                  <h3 style={{ marginBottom: '0.5rem' }}>Smart Routing</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Optimized itineraries based strictly on your selected interests.</p>
                </div>
                <div className="card">
                  <Wallet size={32} color="var(--accent-primary)" style={{ marginBottom: '1rem' }}/>
                  <h3 style={{ marginBottom: '0.5rem' }}>Budget Engine</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Known costs are summed in Python; missing prices remain unavailable.</p>
                </div>
              </div>
            </div>
          )}

          {loading && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '400px' }}>
              <Loader2 className="spinner" size={48} color="var(--accent-primary)" style={{ marginBottom: '1.5rem' }} />
              <h3 className="gradient-text">Analyzing routes and fetching live data...</h3>
            </div>
          )}

          {error && (
            <div className="card" style={{ borderColor: 'var(--danger)', backgroundColor: 'rgba(239,68,68,0.05)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--danger)', marginBottom: '1rem' }}>
                <AlertCircle size={24} />
                <h2>Error</h2>
              </div>
              <p>{error}</p>
            </div>
          )}

          {result && !loading && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '2rem' }}>
                <div>
                  <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>Journey to {formData.destination}</h1>
                  {result.weather?.condition && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                      <span className="badge badge-success">LIVE WEATHER</span>
                      <span>{result.weather.temperature}°C, {result.weather.condition}</span>
                    </div>
                  )}
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Known subtotal</div>
                  <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--success)' }}>{result.budget.entries.some(entry => entry.amount !== null) ? `INR ${result.budget.known_subtotal.toLocaleString()}` : 'Unavailable'} ({result.budget.status})</div>
                </div>
              </div>

              {result.warnings && result.warnings.length > 0 && (
                <div style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid var(--warning)', padding: '1rem', borderRadius: '8px', marginBottom: '2rem', color: '#FCD34D' }}>
                  {result.warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
                </div>
              )}

              {result.metadata.planning_status === 'FAILED' && <p role="alert">No itinerary was generated. Check the model/API warnings.</p>}
              {result.metadata.planning_status === 'PARTIAL' && <p role="status">This itinerary is incomplete.</p>}
              <Tabs result={result} formData={formData} />
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Tabs({ result }) {
  return <div>
    {result.days.map(day => <article className="card" key={day.day} style={{marginBottom: '1rem'}}>
      <h2>Day {day.day} · {day.date} · {day.location}</h2>
      <p>{day.weather?.success ? `${day.weather.temperature}°C · ${day.weather.condition ?? 'condition unavailable'}` : 'Weather unavailable'}</p>
      {['morning','afternoon','evening','places','food','temples'].map(key => <section key={key}>
        <h3>{key}</h3><ul>{day[key].map(item => <li key={item.candidate_id}><a href={item.url} target="_blank" rel="noreferrer">{item.name}</a><p>{item.description}</p></li>)}</ul>
      </section>)}
      {day.warnings.map((warning,i)=><p key={i}>{warning}</p>)}
    </article>)}
    <h2>Transport</h2>{result.transport.map(leg=><div className="card" key={leg.id}>{leg.origin} → {leg.destination} · {leg.departure_date}<p>{leg.result?.success ? `${leg.mode} · ${leg.result.price ?? 'Price unavailable'} ${leg.result.currency ?? ''} (${leg.result.source_type})` : leg.result?.reason ?? 'Not searched; unavailable'}</p>{leg.result?.fares && <><p>Reported railway distance: {leg.result.distance_km} km · {leg.result.distance?.source}</p><ul>{leg.result.fares.map(fare => <li key={fare.class}>{fare.name}: INR {fare.base_fare} + tax {fare.tax} = {fare.total_fare} per traveler · party total {fare.party_total} · CONFIGURED_ESTIMATE</li>)}</ul></>}</div>)}
    <h2>Accommodation</h2>{result.accommodation.map(stay=><div className="card" key={stay.id}>{stay.location} · {stay.check_in} → {stay.check_out}<p>{stay.result?.name ?? stay.result?.reason ?? 'Unavailable'}</p><p>Total: {stay.result?.total_price ?? 'Unavailable'} {stay.result?.currency ?? ''}</p></div>)}
    <h2>Budget: {result.budget.status}</h2><p>Known subtotal: {result.budget.entries.some(entry => entry.amount !== null) ? `INR ${result.budget.known_subtotal}` : 'Unavailable; no prices retrieved'}</p>
    <ul>{result.budget.entries.map((entry,i)=><li key={i}>{entry.label}: {entry.amount ?? 'Unavailable'} · {entry.provenance}</li>)}</ul>
    <details><summary>Tool trace and selection audit</summary><pre>{JSON.stringify({trace:result.tool_trace, randomization:result.randomization},null,2)}</pre></details>
  </div>;
}
export default App;
