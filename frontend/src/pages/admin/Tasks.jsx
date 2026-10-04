import {useEffect,useMemo,useState} from 'react';
import {useData} from '../../context/DataContext.jsx';
import {Card} from '../../components/Ui.jsx';
import {adminService} from '../../services/adminService.js';
import {taskService} from '../../services/taskService.js';

export default function Tasks(){
  const {machines}=useData();
  const [users,setUsers]=useState([]),[tasks,setTasks]=useState([]);
  const [form,setForm]=useState({title:'',description:'',machine_id:'',assigned_to:'',due_date:''});
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  const activeMachines=machines.filter(machine=>machine.status!=='inactive');
  const operators=useMemo(()=>users.filter(user=>user.role==='operator'&&user.active!==false),[users]);
  const load=async()=>{const [people,items]=await Promise.all([adminService.users(),taskService.list()]);setUsers(people);setTasks(items)};
  useEffect(()=>{let mounted=true;const refresh=()=>Promise.all([adminService.users(),taskService.list()]).then(([people,items])=>{if(mounted){setUsers(people);setTasks(items)}}).catch(e=>{if(mounted)setError(e.message||'Could not load tasks')});refresh();const timer=setInterval(refresh,8000);return()=>{mounted=false;clearInterval(timer)}},[]);
  const create=async e=>{e.preventDefault();setError('');if(!form.title.trim()||!form.machine_id||!form.assigned_to){setError('Enter a task title, machine, and assigned operator.');return}setBusy(true);try{const operator=operators.find(person=>person.id===form.assigned_to);await taskService.create({...form,title:form.title.trim(),description:form.description.trim(),due_date:form.due_date||null,assigned_to_name:operator?.name});setForm({...form,title:'',description:'',due_date:''});await load()}catch(err){setError(err.message||'Could not create task')}finally{setBusy(false)}};
  const updateStatus=async(id,status)=>{setError('');try{await taskService.setStatus(id,status);await load()}catch(err){setError(err.message||'Could not update task')}};
  return <div className="grid">
    <Card wide title="🧰 Assign an operator task" badge={import.meta.env.VITE_USE_LIVE_AUTH==='true'?'MongoDB':'Demo'}>
      <p className="mut">Choose any registered operator. Assigning the task also links the selected machine to that operator, so the task appears in their account.</p>
      {error&&<div className="err" role="alert">{error}</div>}
      <form className="device-form" onSubmit={create}>
        <div><label htmlFor="task-title">Task</label><input id="task-title" maxLength="160" value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="Inspect coolant system" required/></div>
        <div><label htmlFor="task-machine">Machine</label><select id="task-machine" value={form.machine_id} onChange={e=>setForm({...form,machine_id:e.target.value,assigned_to:''})} required><option value="">Choose a machine</option>{activeMachines.map(m=><option key={m.id} value={m.id}>{m.n} · {m.id}</option>)}</select></div>
        <div><label htmlFor="task-operator">Assigned operator</label><select id="task-operator" value={form.assigned_to} onChange={e=>setForm({...form,assigned_to:e.target.value})} disabled={!form.machine_id} required><option value="">{form.machine_id?'Choose a registered operator':'Choose a machine first'}</option>{operators.map(person=><option key={person.id} value={person.id}>{person.name} · {person.id}{(person.machines||[]).includes(form.machine_id)?' · linked':' · will be linked'}</option>)}</select></div>
        <div><label htmlFor="task-due">Due date (optional)</label><input id="task-due" type="date" value={form.due_date} onChange={e=>setForm({...form,due_date:e.target.value})}/></div>
        <div style={{gridColumn:'1 / -1'}}><label htmlFor="task-description">Details (optional)</label><textarea id="task-description" rows="2" maxLength="1000" value={form.description} onChange={e=>setForm({...form,description:e.target.value})} placeholder="Add steps or useful context"/></div>
        <button className="p" disabled={busy||!operators.length}>{busy?'Assigning…':'Assign task'}</button>
      </form>
      {form.machine_id&&!operators.length&&<p className="mut">No registered operators are available. Register an operator first in People.</p>}
    </Card>
    <Card wide title="📋 Assigned tasks"><div className="table-scroll"><table><thead><tr><th>Task</th><th>Machine</th><th>Operator</th><th>Due</th><th>Status</th></tr></thead><tbody>{tasks.map(task=><tr key={task.id}><td><b>{task.title}</b>{task.description&&<div className="mut">{task.description}</div>}</td><td>{task.machine_name||task.machine_id}</td><td>{task.assigned_to_name||task.assigned_to}<div className="mut">{task.assigned_to}</div></td><td>{task.due_date||'—'}</td><td><select aria-label={'Status for '+task.title} style={{width:'auto'}} value={task.status} onChange={e=>updateStatus(task.id,e.target.value)}><option>Pending</option><option>In Progress</option><option>Completed</option></select></td></tr>)}{!tasks.length&&<tr><td colSpan="5" className="mut">No tasks assigned yet.</td></tr>}</tbody></table></div></Card>
  </div>;
}
