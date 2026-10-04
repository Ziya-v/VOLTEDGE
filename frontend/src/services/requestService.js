import {api} from './api.js';
const LIVE_REQUESTS=import.meta.env.VITE_USE_LIVE_AUTH==='true';
let mock=[{id:'R1',m:'M3',by:'EMP1042',type:'eco',reason:'Continuous operation required',obs:['Unexpected energy consumption'],fb:'',acts:['Check leakage','Review setpoint','Schedule maintenance'],status:'Pending',log:['Pending · EMP1042']}];
export const STATUSES=['Pending','Approved','Changes Requested','Rejected','Completed'];
export const requestService={
async list(){return LIVE_REQUESTS?api.get('/requests'):[...mock]},
async create(r){if(LIVE_REQUESTS)return api.post('/requests',r);const n=Math.max(0,...mock.map(x=>+x.id.slice(1)))+1;mock=[{...r,id:'R'+n,status:'Pending',log:['Pending · '+r.by]},...mock]},
async setStatus(id,status,by){if(LIVE_REQUESTS)return api.patch('/requests/'+encodeURIComponent(id),{status});mock=mock.map(r=>r.id===id?{...r,status,log:[...r.log,status+' · '+by]}:r)}};
