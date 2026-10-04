import {api} from './api.js';

const LIVE=import.meta.env.VITE_USE_LIVE_AUTH==='true';
const STORAGE_KEY='ve.demo.alertReports';
const DEMO=[
  {id:'demo-temp-M2',m:'M2',machine_name:'Compressor-01',s:'warn',severity:'warning',txt:'Temperature above normal',pr:2,source:'Telemetry detection',status:'Detected'},
  {id:'demo-idle-M4',m:'M4',machine_name:'Chiller-01',s:'warn',severity:'warning',txt:'Chiller idle but drawing power',pr:1,source:'Telemetry detection',status:'Detected'},
  {id:'demo-vibration-M3',m:'M3',machine_name:'CNC Machine 3',s:'warn',severity:'warning',txt:'Vibration rising',pr:3,source:'Telemetry detection',status:'Detected'},
];
const readDemo=()=>{try{return JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]')}catch{return[]}};
const saveDemo=items=>localStorage.setItem(STORAGE_KEY,JSON.stringify(items));

export const alertService={
  async list(){
    if(LIVE)return api.get('/alerts');
    let user=null;try{user=JSON.parse(localStorage.getItem('ve.user')||'null')}catch{}
    const reports=readDemo();
    return user?.role==='admin'?[...DEMO,...reports]:reports.filter(a=>a.reported_by===user?.id||a.assigned_to===user?.id);
  },
  async create(report){
    if(LIVE)return api.post('/alerts',report);
    const user=JSON.parse(localStorage.getItem('ve.user')||'null');
    const reports=readDemo();
    const duplicate=reports.find(a=>a.reported_by===user?.id&&a.m===report.machine_id&&a.rule_id===report.rule_id&&a.status!=='Resolved');
    if(duplicate){duplicate.occurrences=(duplicate.occurrences||1)+1;duplicate.last_detected_at=new Date().toISOString();duplicate.txt=report.message;saveDemo(reports);return duplicate}
    const item={id:'demo-alert-'+Date.now(),m:report.machine_id,machine_name:report.machine_name,s:report.severity==='critical'?'bad':'warn',severity:report.severity,txt:report.message,pr:report.severity==='critical'?0:1,source:'Operator report',status:'Open',reported_by:user?.id,reported_by_name:user?.name,assigned_to:null,rule_id:report.rule_id,created_at:new Date().toISOString(),occurrences:1};
    saveDemo([item,...reports]);return item;
  },
  async update(id,updates){
    if(LIVE)return api.patch('/alerts/'+encodeURIComponent(id),updates);
    const reports=readDemo().map(item=>item.id===id?{...item,...updates}:item);saveDemo(reports);return reports.find(item=>item.id===id);
  },
};
