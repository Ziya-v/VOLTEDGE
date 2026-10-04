import { MOCK, api } from './api.js';
import { MACHINES } from './mock/machines.js';
import { normalizeMachine } from '../engine/machineSchema.js';

const LIVE = import.meta.env.VITE_USE_LIVE_MACHINES === 'true';
let mock = MACHINES.map(normalizeMachine), critDemo = false;
const base = Object.fromEntries(MACHINES.map(m => [m.id, m.temp]));
const defined = o => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined));

export const machineService = {
  async list() {
    return LIVE ? (await api.get('/machines')).map(normalizeMachine) : mock.map(m => ({ ...m }));
  },
  // Live telemetry can be added later through the configured WebSocket.
  subscribe(cb) {
    let cur = [], stop = false, ws, timer;
    const push = () => cb((LIVE ? cur : mock).map(m => ({ ...m })));
    machineService.list().then(l => {
      if (stop) return;
      cur = l;
      cb((LIVE ? cur : mock).map(m => ({ ...m })), null);
      if (!LIVE) {
        timer = setInterval(() => {
          mock = mock.map(m => ({ ...m, kw: Math.max(m.kw0 * .97, Math.min(m.kw0 * 1.03, m.kw + (Math.random() - .5) * m.kw0 * .02)), temp: critDemo && m.id === 'M2' ? 92 : (base[m.id] ?? m.temp) }));
          push();
        }, 2000);
      } else if (import.meta.env.VITE_WS_URL) {
        ws = new WebSocket(import.meta.env.VITE_WS_URL + '?token=' + localStorage.getItem('ve.token'));
        ws.onmessage = e => {
          const d = JSON.parse(e.data);
          if (d.type !== 'reading') return;
          const p = normalizeMachine({ machineId: d.machineId, ...d.reading });
          cur = cur.map(m => m.id === d.machineId ? { ...m, ...defined({ kw: p.kw, pf: p.pf, temp: p.temp, voltage: p.voltage, current: p.current, energy: p.energy, status: p.status }) } : m);
          push();
        };
      } else {
        timer = setInterval(() => machineService.list().then(l => { cur = l; cb((LIVE ? cur : mock).map(m => ({ ...m })), null); }).catch(() => {}), 5000);
      }
    }).catch(error => { cb([], error); if (LIVE && !stop) timer = setInterval(() => machineService.list().then(l => { cur = l; cb((LIVE ? cur : mock).map(m => ({ ...m })), null); }).catch(() => {}), 5000); });
    return () => { stop = true; clearInterval(timer); if (ws) ws.close(); };
  },
  setDemoCritical: v => { critDemo = v; },
  async add(raw) {
    if (!LIVE) {
      mock = [...mock, normalizeMachine({ ...raw, id: 'M' + (mock.length + 1) })];
      return;
    }
    await api.post('/machines', {
      name: raw.machineName,
      machine_type: raw.machineType,
      rated_power: Number(raw.ratedPower),
      power: Number(raw.power),
      units_per_hour: Number(raw.unitsPerHour),
      operational_constraint: raw.operationalConstraint,
      power_factor: Number(raw.powerFactor),
      temperature: Number(raw.temperature),
      baseline_temp: Number(raw.baselineTemp),
      baseline_kwh_per_unit: Number(raw.baselineKwhPerUnit),
      status: 'active',
    });
  },
};

