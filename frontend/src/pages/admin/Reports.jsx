import {useState} from 'react';
import {useApp} from '../../context/AppContext.jsx';
import {useData} from '../../context/DataContext.jsx';
import {useAuth} from '../../context/AuthContext.jsx';
import {Card,DateFilter,ErrorState,EmptyState,Pill,demoTag} from '../../components/Ui.jsx';
import {validRange} from '../../hooks/useSeries.js';
import {reportService,LIVE_REPORTS} from '../../services/reportService.js';

const TYPES=[
  {id:'Energy',icon:'⚡',hint:'Consumption, cost and emissions over time'},
  {id:'Machine',icon:'🏭',hint:'Energy use and efficiency by machine'},
  {id:'Sustainability',icon:'🌱',hint:'CO₂ impact and energy intensity'},
  {id:'Maintenance',icon:'🔧',hint:'Maintenance schedule and open recommendations'},
  {id:'Anomalies',icon:'🚨',hint:'Incident details, employee identities and sensor readings'},
];
const csvCell=value=>'"'+String(value??'').replaceAll('"','""')+'"';

function ReportBars({rows,values}){
  if(!values?.length)return <div className="report-chart-empty">No chart values in this report.</div>;
  const max=Math.max(...values.map(Number),1),labels=rows.map(row=>String(row?.[0]??''));
  return <div className="report-bars" role="img" aria-label="Report values by category">
    {values.map((raw,index)=>{const value=Number(raw)||0;return <div className="report-bar-column" key={index} title={`${labels[index]||`Item ${index+1}`}: ${value.toLocaleString('en-IN')}`}>
      <b>{value.toLocaleString('en-IN',{maximumFractionDigits:1})}</b>
      <div className="report-bar-track"><i style={{height:`${Math.max(4,value/max*100)}%`}}/></div>
      <span>{labels[index]||`Item ${index+1}`}</span>
    </div>})}
  </div>;
}

export default function Reports(){
  const {toast}=useApp(),{machines,tariff}=useData(),{user}=useAuth();
  const visibleMachines=user?.role==='operator'?machines.filter(m=>(user.machines||[]).includes(m.id)):machines;
  const [range,setRange]=useState({rg:'7D',from:'',to:''}),[type,setType]=useState('Energy'),[mid,setMid]=useState('all');
  const [rep,setRep]=useState(null),[err,setErr]=useState(''),[busy,setBusy]=useState(false);
  const selectedType=TYPES.find(item=>item.id===type)||TYPES[0];
  const clearReport=()=>{setRep(null);setErr('')};
  const gen=async()=>{setBusy(true);setErr('');try{setRep(await reportService.generate(type,mid,range,tariff,visibleMachines));toast('✔ Report ready')}catch(e){setErr(e.message||'Could not generate report')}finally{setBusy(false)}};
  const csv=()=>{
    if(!rep)return;
    const contents=[rep.cols,...rep.rows].map(row=>row.map(csvCell).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob(['\uFEFF'+contents],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download=`voltedge-${rep.type.toLowerCase()}-report.csv`;link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  const ready=!!visibleMachines.length&&validRange(range);
  return <div className="report-page">
    <section className="report-welcome">
      <div><div className="report-eyebrow">VOLTEDGE · OPERATIONS</div><h2>Reports</h2>
        <p>Turn machine and telemetry data into a clear, shareable report.</p></div>
      <Pill>{LIVE_REPORTS?'MongoDB live data':demoTag||'Demo data'}</Pill>
    </section>

    <Card title="Build a report" badge="Step 1 · Choose your view">
      <div className="report-type-grid" role="group" aria-label="Report type">
        {TYPES.map(item=><button type="button" key={item.id} aria-pressed={type===item.id}
          className={`report-type ${type===item.id?'selected':''}`} onClick={()=>{setType(item.id);clearReport()}}>
          <span>{item.icon}</span><b>{item.id}</b><small>{item.hint}</small>
        </button>)}
      </div>
      <div className="report-filters">
        <div><label htmlFor="report-machine">Machines</label><select id="report-machine" value={mid} onChange={e=>{setMid(e.target.value);clearReport()}}>
          <option value="all">{user?.role==='operator'?'All my assigned machines':'All machines'}</option>
          {visibleMachines.map(machine=><option key={machine.id} value={machine.id}>{machine.n}</option>)}
        </select></div>
        <div><label>Reporting period</label><DateFilter value={range} onChange={value=>{setRange(value);clearReport()}}/></div>
      </div>
      <div className="report-actions"><div className="mut">{selectedType.icon} {selectedType.hint}{type==='Energy'&&` · Tariff ₹${tariff}/kWh`}</div>
        <button className="p" disabled={!ready||busy} onClick={gen}>{busy?'Generating…':'Generate report →'}</button></div>
    </Card>

    {!visibleMachines.length&&<EmptyState>No machines are assigned to your account yet. Ask your admin to assign one in People.</EmptyState>}
    {err&&<ErrorState msg={err}/>}
    {!rep&&visibleMachines.length>0&&<section className="report-empty card"><span>📑</span><div><b>Your report will appear here</b><p className="mut">Choose a report type and date range, then generate it. You can export the result as CSV or print it to PDF.</p></div></section>}

    {rep&&<section id="prev" className="report-result">
      <div className="report-result-heading"><div><div className="report-eyebrow">GENERATED REPORT</div><h2>{rep.title}</h2>
        <p className="mut">{rep.range} · {rep.mname}{rep.generatedAt&&` · Created ${new Date(rep.generatedAt).toLocaleString()}`}</p></div>
        <div className="row noprint"><button className="p" onClick={csv}>⬇ Export CSV</button><button onClick={()=>window.print()}>🖨 Print / PDF</button></div>
      </div>
      <div className="report-kpis">{rep.sum.map((item,index)=><div className="report-kpi" key={item[0]}><span>{['📊','💰','🌿','🏭'][index%4]}</span><b>{item[1]}</b><small>{item[0]}</small></div>)}</div>
      {rep.truncated&&<div className="item warn" role="status">This report contains more incidents than can be displayed at once. The table shows the newest 2,000 of {rep.totalRecords} matching reports.</div>}
      <Card title="At a glance"><ReportBars rows={rep.chartRows||rep.rows} values={rep.chart}/></Card>
      <Card title="Detailed breakdown"><div className="table-scroll"><table><thead><tr>{rep.cols.map(col=><th key={col}>{col}</th>)}</tr></thead>
        <tbody>{rep.rows.map((row,index)=><tr key={index}>{row.map((cell,col)=>col===0?<th scope="row" key={col}>{cell}</th>:<td key={col}>{cell}</td>)}</tr>)}
        {!rep.rows.length&&<tr><td className="mut" colSpan={rep.cols.length}>No records were found for this range.</td></tr>}</tbody></table></div></Card>
      <p className="report-footnote">{type==='Anomalies'?'This incident log contains anomaly reports submitted by operators, including the employee identity, machine, status, occurrence count, and readings attached to the report.':'Report values are calculated from telemetry available for the selected period.'} Demo meter readings are simulated and labeled as demo data.</p>
    </section>}
  </div>;
}
