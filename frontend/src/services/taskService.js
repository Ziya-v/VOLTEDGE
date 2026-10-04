import {api} from './api.js';

const LIVE_TASKS=import.meta.env.VITE_USE_LIVE_AUTH==='true';
let demoTasks=[];

export const taskService={
  async list(){
    if(LIVE_TASKS)return api.get('/tasks');
    let user=null;try{user=JSON.parse(localStorage.getItem('ve.user')||'null')}catch{}
    return user?.role==='admin'?demoTasks:demoTasks.filter(task=>task.assigned_to===user?.id);
  },
  async create(task){
    if(LIVE_TASKS)return api.post('/tasks',task);
    const created={id:'demo-'+Date.now(),...task,machine_name:task.machine_name||task.machine_id,assigned_to_name:task.assigned_to_name||task.assigned_to,status:'Pending',created_at:new Date().toISOString()};
    demoTasks=[created,...demoTasks];return created;
  },
  async setStatus(id,status){
    if(LIVE_TASKS)return api.patch('/tasks/'+encodeURIComponent(id),{status});
    demoTasks=demoTasks.map(task=>task.id===id?{...task,status}:task);
    return demoTasks.find(task=>task.id===id);
  },
};
