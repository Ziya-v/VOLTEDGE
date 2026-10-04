import {createContext,useCallback,useContext,useEffect,useState} from 'react';
import {machineService} from '../services/machineService.js';import {recommendationService} from '../services/recommendationService.js';
import {requestService} from '../services/requestService.js';import {adminService} from '../services/adminService.js';
const Ctx=createContext();export const useData=()=>useContext(Ctx);
export function DataProvider({children}){
const [machines,setMachines]=useState([]),[machinesLoading,setMachinesLoading]=useState(true),[machinesError,setMachinesError]=useState(''),[recs,setRecs]=useState({}),[requests,setRequests]=useState([]),[extra,setExtra]=useState([]),[tariff,setTariff]=useState(8.5);
useEffect(()=>machineService.subscribe((items,error)=>{setMachines(items);setMachinesLoading(false);setMachinesError(error?.message||'');}),[]);
useEffect(()=>{let on=true;Promise.all(machines.map(m=>recommendationService.get(m,tariff).then(r=>[m.id,r]))).then(e=>on&&setRecs(Object.fromEntries(e)));return()=>{on=false}},[machines,tariff]);
const reload=useCallback(()=>requestService.list().then(setRequests),[]);
const reloadAlerts=useCallback(()=>adminService.alerts().then(setExtra).catch(()=>{}),[]);
useEffect(()=>{reload();reloadAlerts();const timer=setInterval(reloadAlerts,5000);return()=>clearInterval(timer)},[reload,reloadAlerts]);
const crit=import.meta.env.VITE_USE_LIVE_AUTH==='true'?[]:machines.flatMap(m=>(recs[m.id]||[]).filter(r=>r.esc).map(r=>({id:'c'+m.id,m:m.id,s:'bad',txt:r.esc,pr:0})));
const alerts=[...crit,...extra].sort((a,b)=>a.pr-b.pr);
return <Ctx.Provider value={{machines,machinesLoading,machinesError,recs,requests,reload,alerts,reloadAlerts,tariff,setTariff}}>{children}</Ctx.Provider>}
