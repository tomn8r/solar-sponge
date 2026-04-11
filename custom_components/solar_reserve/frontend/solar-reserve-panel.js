class SolarReservePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this.entities = {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
      this.init();
    }
    this.updateData();
  }

  init() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 16px;
          font-family: var(--paper-font-body1_-_font-family), -apple-system, Roboto, sans-serif;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          min-height: 100vh;
          box-sizing: border-box;
          overflow-y: auto;
        }
        * { box-sizing: border-box; }
        
        .dashboard-container {
          max-width: 1200px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 16px;
          padding-bottom: 30px;
        }

        .header {
          padding: 16px 8px 8px 8px;
        }
        
        .header h1 {
          font-size: 2rem;
          font-weight: 400;
          margin: 0;
          color: var(--primary-text-color);
        }

        .card {
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0px 2px 1px -1px rgba(0, 0, 0, 0.2), 0px 1px 1px 0px rgba(0, 0, 0, 0.14), 0px 1px 3px 0px rgba(0, 0, 0, 0.12));
          padding: 16px;
        }
        
        .card-header {
          font-size: 1.25rem;
          font-weight: 500;
          margin-bottom: 16px;
          color: var(--primary-text-color);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .grid-2 {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }

        @media (max-width: 768px) {
          .grid-2 { grid-template-columns: 1fr; }
        }

        .metric-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 0;
          border-bottom: 1px solid var(--divider-color, rgba(0,0,0,0.12));
          font-size: 1rem;
        }
        .metric-row:last-child {
          border-bottom: none;
        }
        
        .metric-row.sub-row {
          padding-left: 24px;
          font-size: 0.9rem;
          color: var(--secondary-text-color);
        }
        
        .metric-row.total-row {
          font-weight: bold;
          border-top: 2px solid var(--divider-color, rgba(0,0,0,0.12));
          border-bottom: none;
          padding-top: 12px;
          margin-top: 8px;
        }

        .value {
          font-weight: 500;
        }

        /* Large Status Displays */
        .status-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 24px 0;
        }

        .status-value {
          font-size: 3rem;
          font-weight: 500;
          line-height: 1.2;
        }
        
        .status-label {
          color: var(--secondary-text-color);
          font-size: 1rem;
        }
        
        .status-on { color: var(--success-color, #4caf50); }
        .status-off { color: var(--error-color, #f44336); }
        .status-neutral { color: var(--primary-color, #03a9f4); }

        .chip {
          background: var(--secondary-background-color);
          padding: 4px 12px;
          border-radius: 16px;
          font-size: 0.85rem;
          color: var(--secondary-text-color);
        }
      </style>

      <div class="dashboard-container">
        <div class="header">
          <h1>HA Solar Reserve Analytics</h1>
        </div>

        <!-- Master Output Row -->
        <div class="grid-2">
          <div class="card">
            <div class="card-header">Master Output</div>
            <div class="grid-2">
              <div class="status-container">
                <div class="status-label">Permission</div>
                <div id="permission-status" class="status-value status-off">-</div>
              </div>
              <div class="status-container">
                <div class="status-label">Calculated Surplus</div>
                <div id="surplus-val" class="status-value status-neutral">-</div>
                <div class="status-label">kWh</div>
              </div>
            </div>
          </div>
          
          <div class="card">
            <div class="card-header">System Intel</div>
            <div class="metric-row">
              <span>Estimated Runtime Remaining</span>
              <span id="runtime-val" class="value">-</span>
            </div>
            <div class="metric-row">
              <span>Data Warmup Nights (Max 7)</span>
              <span id="warmup-night" class="value">-</span>
            </div>
            <div class="metric-row">
              <span>Data Warmup Days (Max 7)</span>
              <span id="warmup-day" class="value">-</span>
            </div>
          </div>
        </div>

        <!-- The Equation Breakdown -->
        <div class="grid-2">
          <!-- Assets -->
          <div class="card">
            <div class="card-header">Energy Assets (Available)</div>
            <div class="metric-row">
              <span>Current Battery Charge</span>
              <span id="batt-charge" class="value">-</span>
            </div>
            <div class="metric-row sub-row">
              <span>Resolved Capacity Utilized</span>
              <span id="batt-cap" class="value">-</span>
            </div>
            <div class="metric-row">
              <span>Solar Remaining Today (Est.)</span>
              <span id="solar-today" class="value">-</span>
            </div>
            <div class="metric-row total-row">
              <span>Total Energy Available</span>
              <span id="total-assets" class="value" style="color: var(--success-color, #4caf50);">-</span>
            </div>
          </div>

          <!-- Liabilities -->
          <div class="card">
            <div class="card-header">Energy Liabilities (Required)</div>
            <div class="metric-row">
              <span>Dynamic Expected Load</span>
              <span id="exp-load" class="value">-</span>
            </div>
            <div class="metric-row sub-row">
              <span>Target Config: (Night + Next Day Buffers)</span>
            </div>
            <div class="metric-row">
              <span>Tomorrow's Deficit</span>
              <span id="tom-deficit" class="value">-</span>
            </div>
            <div class="metric-row sub-row">
              <span>Expected Tomorrow (Day+Night)</span>
              <span id="tom-expected" class="value">-</span>
            </div>
            <div class="metric-row sub-row">
              <span>Solar Output Tomorrow</span>
              <span id="solar-tom" class="value">-</span>
            </div>
            <div class="metric-row total-row">
              <span>Total Energy Required</span>
              <span id="total-liab" class="value" style="color: var(--error-color, #f44336);">-</span>
            </div>
          </div>
        </div>

        <!-- Historical Breakdown -->
        <div class="card">
          <div class="card-header">Load Trackers & Diagnostics</div>
          <div class="grid-2">
            <div>
              <div class="metric-row">
                <span>Overnight Usage (Current/Last)</span>
                <span id="night-actual" class="value">-</span>
              </div>
              <div class="metric-row sub-row">
                <span>Rolling 7-Night Average</span>
                <span id="night-avg" class="value">-</span>
              </div>
              <div class="metric-row sub-row">
                <span>Sunset Energy Snapshot</span>
                <span id="sunset-snap" class="value">-</span>
              </div>
            </div>
            <div>
              <div class="metric-row">
                <span>Daytime Usage (Current/Last)</span>
                <span id="day-actual" class="value">-</span>
              </div>
              <div class="metric-row sub-row">
                <span>Rolling 7-Day Average</span>
                <span id="day-avg" class="value">-</span>
              </div>
              <div class="metric-row sub-row">
                <span>Sunrise Energy Snapshot</span>
                <span id="sunrise-snap" class="value">-</span>
              </div>
            </div>
          </div>
          <div style="margin-top: 16px; border-top: 1px solid var(--divider-color, rgba(0,0,0,0.12)); padding-top: 16px;">
            <div class="metric-row">
              <span>Managed Load Usage Segment</span>
              <span id="managed-load" class="value">-</span>
            </div>
            <div class="metric-row sub-row">
              <span>Used since last horizon crossing</span>
            </div>
          </div>
        </div>

        <!-- Raw Configuration Inputs -->
        <div class="card">
          <div class="card-header">Raw Configuration Inputs</div>
          <div class="grid-2">
            <div>
              <div class="metric-row">
                <span>Total Home Energy (Cumulative)</span>
                <span id="raw-home" class="value">-</span>
              </div>
              <div class="metric-row">
                <span>Managed Load Sensor (Cumulative)</span>
                <span id="raw-managed" class="value">-</span>
              </div>
              <div class="metric-row">
                <span>Battery Status Sensor (Raw)</span>
                <span id="raw-battery" class="value">-</span>
              </div>
            </div>
            <div>
              <div class="metric-row">
                <span>Solar Forecast Remaining Today</span>
                <span id="raw-solar-today" class="value">-</span>
              </div>
              <div class="metric-row">
                <span>Solar Forecast Tomorrow</span>
                <span id="raw-solar-tom" class="value">-</span>
              </div>
              <div class="metric-row">
                <span>Rated Energy Capacity</span>
                <span id="raw-cap" class="value">-</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    `;
    this.content = true;
  }

  updateData() {
    if (!this._hass) return;

    const states = this._hass.states;
    let data = {};

    for (const [entityId, stateObj] of Object.entries(states)) {
      if (entityId.includes('solar_reserve')) {
        if (entityId.includes('solar_reserve_permission')) data.permission = stateObj;
        else if (entityId.includes('calculated_surplus')) data.surplus = stateObj;
        else if (entityId.includes('energy_available')) data.available = stateObj;
        else if (entityId.includes('energy_required')) data.required = stateObj;
        else if (entityId.includes('average_overnight_load')) data.avgNight = stateObj;
        else if (entityId.includes('overnight_load_tracker')) data.actNight = stateObj;
        else if (entityId.includes('average_daytime_load')) data.avgDay = stateObj;
        else if (entityId.includes('daytime_load_tracker')) data.actDay = stateObj;
        else if (entityId.includes('resolved_battery_capacity')) data.batteryCap = stateObj;
        else if (entityId.includes('managed_load_usage')) data.managed = stateObj;
        else if (entityId.includes('night_data_days')) data.nightDays = stateObj;
        else if (entityId.includes('day_data_days')) data.dayDays = stateObj;
      }
    }

    // Helper formatting
    const fw = (val, dec = 2) => val !== undefined && val !== null ? parseFloat(val).toFixed(dec) + ' kWh' : '-';

    if (data.permission) {
      const el = this.shadowRoot.getElementById('permission-status');
      el.innerText = data.permission.state.toUpperCase();
      el.className = data.permission.state === 'on' ? 'status-value status-on' : 'status-value status-off';
      
      const attrs = data.permission.attributes;
      this.shadowRoot.getElementById('runtime-val').innerText = attrs.estimated_runtime_hours !== undefined ? attrs.estimated_runtime_hours + ' hrs' : '-';
      
      // Dynamic loads
      this.shadowRoot.getElementById('exp-load').innerText = fw(attrs.dynamic_expected_load_kwh);
      this.shadowRoot.getElementById('tom-deficit').innerText = fw(attrs.tomorrow_deficit_kwh);
      
      // Calculate missing variables
      const eDay = parseFloat(attrs.avg_day_load_kwh) || 0;
      const eNight = parseFloat(attrs.avg_night_load_kwh) || 0;
      const tExp = eDay + eNight;

      this.shadowRoot.getElementById('tom-expected').innerText = fw(tExp);
      this.shadowRoot.getElementById('solar-tom').innerText = fw(attrs.raw_solar_tomorrow);
      
      // Update Raw Config Inputs
      this.shadowRoot.getElementById('raw-home').innerText = fw(attrs.raw_home_energy);
      this.shadowRoot.getElementById('raw-managed').innerText = fw(attrs.raw_managed_load);
      this.shadowRoot.getElementById('raw-solar-today').innerText = fw(attrs.raw_solar_today);
      this.shadowRoot.getElementById('raw-solar-tom').innerText = fw(attrs.raw_solar_tomorrow);
      this.shadowRoot.getElementById('raw-battery').innerText = attrs.raw_battery_percent !== undefined && attrs.raw_battery_percent !== null ? attrs.raw_battery_percent + (attrs.raw_battery_percent <= 100 ? '%' : ' kWh') : '-';
      
      // Calculate isolated battery
      if (data.batteryCap) {
        const rawSolarToday = parseFloat(attrs.raw_solar_today);
        const rawBattery = parseFloat(attrs.raw_battery_percent);
        const cap = parseFloat(data.batteryCap.state);
        
        // Assume default % evaluation since raw inputs show it, but fallback if it was set to energy
        const currentBattery = (rawBattery <= 100 && cap) ? (cap * rawBattery / 100) : rawBattery;
        
        this.shadowRoot.getElementById('batt-charge').innerText = fw(currentBattery);
        this.shadowRoot.getElementById('solar-today').innerText = fw(rawSolarToday);
      }
    }

    if (data.surplus) this.shadowRoot.getElementById('surplus-val').innerText = parseFloat(data.surplus.state).toFixed(2);
    if (data.available) this.shadowRoot.getElementById('total-assets').innerText = fw(data.available.state);
    if (data.required) this.shadowRoot.getElementById('total-liab').innerText = fw(data.required.state);
    
    // Battery Configs
    if (data.batteryCap) {
      this.shadowRoot.getElementById('batt-cap').innerText = fw(data.batteryCap.state);
      this.shadowRoot.getElementById('raw-cap').innerText = fw(data.batteryCap.state);
    }

    if (data.actNight) {
      this.shadowRoot.getElementById('night-actual').innerText = fw(data.actNight.state);
      this.shadowRoot.getElementById('sunset-snap').innerText = fw(data.actNight.attributes.sunset_snapshot_kwh);
    }
    if (data.avgNight) this.shadowRoot.getElementById('night-avg').innerText = fw(data.avgNight.state);

    if (data.actDay) {
      this.shadowRoot.getElementById('day-actual').innerText = fw(data.actDay.state);
      this.shadowRoot.getElementById('sunrise-snap').innerText = fw(data.actDay.attributes.sunrise_snapshot_kwh);
    }
    if (data.avgDay) this.shadowRoot.getElementById('day-avg').innerText = fw(data.avgDay.state);

    if (data.managed) this.shadowRoot.getElementById('managed-load').innerText = fw(data.managed.state, 3);
    if (data.nightDays) this.shadowRoot.getElementById('warmup-night').innerText = data.nightDays.state;
    if (data.dayDays) this.shadowRoot.getElementById('warmup-day').innerText = data.dayDays.state;
  }
}

customElements.define("solar-reserve-panel", SolarReservePanel);
