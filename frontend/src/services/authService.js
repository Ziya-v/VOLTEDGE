import {api} from './api.js';import {USERS} from './mock/users.js';
const fail=code=>{throw Object.assign(new Error(code),{code})},save=u=>{localStorage.setItem('ve.user',JSON.stringify(u));return u};
const viaApi=async(path,id,pw,role,extra={})=>{const r=await api.post(path,{employeeId:id,password:pw,...extra,...(role?{role}:{})});localStorage.setItem('ve.token',r.token);return save(r.user)};
// Role is returned by the backend; public registration always creates an operator.
export const authService={
current:()=>{if(import.meta.env.VITE_USE_LIVE_AUTH==='true'&&!localStorage.getItem('ve.token')){localStorage.removeItem('ve.user');return null}try{return JSON.parse(localStorage.getItem('ve.user'))}catch{return null}},
async login(id,pw,role){if(import.meta.env.VITE_USE_LIVE_AUTH==='true')return viaApi('/auth/login',id,pw,role);const u=USERS[id];if(!u||u.pw!==pw)fail('e3');if(role&&role!==u.role)throw new Error(`This account is registered as ${u.role}. Choose ${u.role} login.`);return save({id,name:u.name,role:u.role,machines:u.machines})},
async register(id,name,pw){if(import.meta.env.VITE_USE_LIVE_AUTH==='true')return viaApi('/auth/register',id,pw,null,{name});const u=USERS[id];if(!u)fail('e4');if(u.pw)fail('e5');u.pw=pw;return save({id,name:u.name,role:u.role,machines:u.machines})},
async heartbeat(){if(import.meta.env.VITE_USE_LIVE_AUTH==='true'&&localStorage.getItem('ve.token'))return api.post('/auth/heartbeat',{});return null},
async logout(){if(import.meta.env.VITE_USE_LIVE_AUTH==='true'&&localStorage.getItem('ve.token')){try{await api.post('/auth/logout',{})}catch{}}localStorage.removeItem('ve.user');localStorage.removeItem('ve.token')}};

