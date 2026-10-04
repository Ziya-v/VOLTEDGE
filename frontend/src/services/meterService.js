import {MOCK,api} from './api.js';

const keyFor=machineId=>`ve.operator-meter.${machineId}`;
const readLocal=machineId=>{
  try{return JSON.parse(localStorage.getItem(keyFor(machineId))||'{"readings":[]}')}
  catch{return {readings:[]}}
};

export const meterService={
  async latest(machineId){
    if(MOCK)return readLocal(machineId).readings[0]||null;
    try{return await api.get('/telemetry/latest/'+encodeURIComponent(machineId))}
    catch(error){if(error.status===404)return null;throw error}
  },
  async capture(machine){
    const reading={
      machine_id:machine.id,
      power_kw:Number(machine.kw),
      power_factor:Number(machine.pf),
      temperature:Number(machine.temp),
      voltage:machine.voltage==null?undefined:Number(machine.voltage),
      current:machine.current==null?undefined:Number(machine.current),
      energy_kwh:machine.energy==null?undefined:Number(machine.energy),
      source:'operator_meter',
      timestamp:new Date().toISOString(),
    };
    if(!MOCK)return api.post('/telemetry',reading);
    const state=readLocal(machine.id),next={readings:[reading,...state.readings].slice(0,20)};
    localStorage.setItem(keyFor(machine.id),JSON.stringify(next));
    return reading;
  },
};
