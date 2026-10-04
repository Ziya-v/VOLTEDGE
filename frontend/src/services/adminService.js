import {MOCK,api} from './api.js';import {USERS} from './mock/users.js';
import {alertService} from './alertService.js';
const LIVE_USERS=import.meta.env.VITE_USE_LIVE_AUTH==='true';
const DEVICES=['M1','M2','M3','M4','M5'].map((m,i)=>({id:'ESP32-'+(100+i),m,status:i===3?'Weak signal':'Connected',seen:'12 seconds ago'}));
let demoDevices=DEVICES.map(d=>({device_id:d.id,name:d.id,machine_id:d.m,machine_name:d.m,status:d.status==='Connected'?'Connected':'Offline',protocol:'Demo',last_seen:null}));
export const adminService={
async alerts(){return alertService.list()},
async users(){return LIVE_USERS?api.get('/users'):Object.entries(USERS).map(([id,u])=>({id,name:u.name,role:u.role,machines:u.machines,sessionActive:false}))},
async setRole(id,role){if(LIVE_USERS){await api.patch('/users/'+id,{role});return}USERS[id].role=role},
async updateUser(id,updates){if(LIVE_USERS)return api.patch('/users/'+encodeURIComponent(id),updates);const user=USERS[id];if(user)Object.assign(user,updates);return user},
async devices(){return LIVE_USERS?api.get('/devices'):demoDevices},
async mqttStatus(){return LIVE_USERS?api.get('/health/mqtt'):{configured:false,connected:false,dependency_available:true,topic:'voltedge/telemetry/+'}},
async demoIotStatus(){return LIVE_USERS?api.get('/demo-iot/status'):{active:false,machines:0}},
async startDemoIot(){return api.post('/demo-iot/start',{})},
async stopDemoIot(){return api.post('/demo-iot/stop',{})},
async createDevice(device){if(LIVE_USERS)return api.post('/devices',device);const d={...device,machine_name:device.machine_id,status:'Offline',protocol:device.protocol||'Demo'};demoDevices=[d,...demoDevices];return d},
async updateDevice(id,updates){if(LIVE_USERS)return api.patch('/devices/'+encodeURIComponent(id),updates);demoDevices=demoDevices.map(d=>d.device_id===id?{...d,...updates}:d)},
async deleteDevice(id){if(LIVE_USERS)return api.delete('/devices/'+encodeURIComponent(id));demoDevices=demoDevices.filter(d=>d.device_id!==id)},
async maintenance(){return LIVE_USERS?api.get('/maintenance'):MOCK?[{m:'Compressor-01',t:'Inspect air filter',st:'lav'},{m:'Compressor-01',t:'Lubrication due in 2 days',st:'lav'},{m:'Chiller-01',t:'Compressor service in 5 days',st:'warn'}]:api.get('/maintenance')}};
