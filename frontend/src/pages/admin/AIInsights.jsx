import {useEffect,useState} from 'react';
import {api} from '../../services/api.js';
import {recommendationService} from '../../services/recommendationService.js';
import {useData} from '../../context/DataContext.jsx';
import {useAuth} from '../../context/AuthContext.jsx';
import {FlowStrip,RecCard,EmptyState,Pill,Loading,Card,LineChart} from '../../components/Ui.jsx';
import {analyticsService} from '../../services/analyticsService.js';

const LIVE=import.meta.env.VITE_USE_LIVE_AUTH==='true';
const statusLabel={ready:'Model ready',warming_up:'Building history',mapping_required:'Choose model asset',unsupported_asset:'Unsupported asset',no_data:'Waiting for data',unavailable:'Unavailable'};
const fmt=(value,digits=3)=>value==null?'—':Number(value).toFixed(digits);

function MLCard({machine,assets,analysis,onMappingChange,onSaveMapping,saving,draft,canConfigure}){
  const status=analysis?.status||'loading';
  const normal=analysis?.status==='ready'&&!analysis.anomaly;
  const tone=status==='ready'?(analysis.anomaly?(analysis.severity==='CRITICAL'||analysis.severity==='HIGH'?'bad':'warn'):'ok'):'warn';
  return <Card title={'🧠 Trained ML · '+machine.n} badge={statusLabel[status]||'Loading'}>
    {canConfigure&&machine.id&&<div className="row" style={{marginBottom:10,flexWrap:'wrap'}}>
      <label htmlFor={'ml-asset-'+machine.id}>Model asset ID</label>
      <select id={'ml-asset-'+machine.id} value={draft??analysis?.ml_asset_id??machine.mlAssetId??''} onChange={e=>onMappingChange(machine.id,e.target.value)} style={{width:'auto',minWidth:180}}>
        <option value="">Choose matching trained asset</option>
        {assets.map(asset=><option key={asset} value={asset}>{asset}</option>)}
      </select>
      <button className="p" disabled={saving||!draft||draft===(analysis?.ml_asset_id??machine.mlAssetId)} onClick={()=>onSaveMapping(machine)}>{saving?'Saving…':'Save mapping'}</button>
    </div>}
    {analysis?.message&&<p className="mut">{analysis.message}</p>}
    {analysis?.status==='ready'&&<>
      <div className="row" style={{marginBottom:10,flexWrap:'wrap'}}><Pill k={tone}>{normal?'No anomaly detected':`${analysis.severity} anomaly detected`}</Pill><Pill k={analysis.telemetry_fresh?'ok':'warn'}>{analysis.telemetry_fresh?'Live data current':'Telemetry is stale'}</Pill><span className="mut">Trained asset: {analysis.ml_asset_id} · Latest completed window: {analysis.window_start_utc?new Date(analysis.window_start_utc).toLocaleString():'—'}</span></div>
      <div className="grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(145px,1fr))'}}>
        <div className="item inf"><small>Actual energy</small><b>{fmt(analysis.actual_energy_kwh)} kWh</b></div>
        <div className="item inf"><small>Model expected</small><b>{fmt(analysis.expected_energy_kwh)} kWh</b></div>
        <div className="item inf"><small>Difference from expected</small><b>{analysis.deviation_percent==null?'—':`${analysis.deviation_percent>=0?'+':''}${fmt(analysis.deviation_percent,1)}%`}</b></div>
        <div className="item inf"><small>Same time previous day</small><b>{fmt(analysis.same_time_previous_day_kwh)} kWh</b></div>
        <div className="item inf"><small>Anomaly score</small><b>{fmt(analysis.anomaly_score,5)}</b></div>
        <div className="item inf"><small>Potential excess</small><b>{fmt(analysis.potential_waste_kwh)} kWh</b></div>
        <div className="item inf"><small>Estimated cost impact</small><b>₹{fmt(analysis.potential_cost_impact_rupees,2)}</b></div>
      </div>
      <h4 style={{margin:'14px 0 8px'}}>Next-hour energy forecast</h4>
      <div className="grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(130px,1fr))'}}>
        {(analysis.forecast_next_hour||[]).map((item,index)=><div className="item inf" key={item.window_start_utc}><small>In {(index+1)*15} minutes</small><b>{fmt(item.expected_energy_kwh)} kWh</b></div>)}
        <div className="item inf"><small>Next-hour total</small><b>{analysis.forecast_next_hour_total_kwh==null?'—':`${fmt(analysis.forecast_next_hour_total_kwh)} kWh`}</b></div>
      </div>
      <h4 style={{margin:'14px 0 8px'}}>Latest window and next-hour forecast</h4>
      <LineChart values={[analysis.actual_energy_kwh,analysis.expected_energy_kwh,...(analysis.forecast_next_hour||[]).map(item=>item.expected_energy_kwh)].map(value=>Number(value)||0)} labels={['Actual','Expected',...(analysis.forecast_next_hour||[]).map((_,index)=>`+${(index+1)*15}m`)]} unit=" kWh"/>
      <p className="mut">Uses {analysis.sample_windows} consecutive 15-minute windows. Later forecast steps reuse earlier predictions, so uncertainty grows with horizon; values are estimates, not guaranteed usage or calibrated confidence bounds. {analysis.telemetry_fresh?'Most recent reading':'Last reading'}: {analysis.last_reading_at?new Date(analysis.last_reading_at).toLocaleString():'unknown'}. Cost estimate uses ₹{fmt(analysis.tariff_rupees_per_kwh,2)}/kWh.</p>
    </>}
  </Card>;
}

export default function AIInsights(){
  const {machines,recs,tariff}=useData(),{user}=useAuth();
  const visibleMachines=user?.role==='operator'?machines.filter(m=>(user.machines||[]).includes(m.id)):machines;
  const [assets,setAssets]=useState([]),[analyses,setAnalyses]=useState({}),[drafts,setDrafts]=useState({}),[saving,setSaving]=useState(''),[error,setError]=useState(''),[analysisSeries,setAnalysisSeries]=useState(null),[analysisBusy,setAnalysisBusy]=useState(false),[analysedAt,setAnalysedAt]=useState(null);
  const machineKey=visibleMachines.map(m=>m.id).join('|');

  useEffect(()=>{
    if(!LIVE||user?.role!=='admin')return;
    let active=true;
    api.get('/ml/assets').then(result=>active&&setAssets(result.assets||[])).catch(e=>active&&setError(e.message||'Could not load trained model assets'));
    return()=>{active=false};
  },[user?.role]);

  useEffect(()=>{
    if(!LIVE||!machineKey)return;
    let active=true;
    const refresh=()=>Promise.all(visibleMachines.map(machine=>api.get('/ml/analysis/'+encodeURIComponent(machine.id)+'?tariff='+encodeURIComponent(tariff||8.0)).then(data=>[machine.id,data]).catch(e=>[machine.id,{status:'unavailable',message:e.message||'Could not load model result'}]))).then(rows=>{
      if(active)setAnalyses(Object.fromEntries(rows));
    });
    refresh();
    const timer=setInterval(refresh,20000);
    return()=>{active=false;clearInterval(timer)};
  },[machineKey,LIVE,tariff]);

  const saveMapping=async machine=>{
    const mlAssetId=drafts[machine.id];
    if(!mlAssetId)return;
    setSaving(machine.id);setError('');
    try{
      await api.patch('/machines/'+encodeURIComponent(machine.id),{ml_asset_id:mlAssetId});
      recommendationService.clearCache(machine.id);
      const result=await api.get('/ml/analysis/'+encodeURIComponent(machine.id)+'?tariff='+encodeURIComponent(tariff||8.0));
      setAnalyses(previous=>({...previous,[machine.id]:result}));
      setDrafts(previous=>{const next={...previous};delete next[machine.id];return next});
    }catch(e){setError(e.message||'Could not save model mapping')}finally{setSaving('')}
  };

  const analyseNow=async()=>{
    if(!visibleMachines.length)return;
    setAnalysisBusy(true);setError('');
    try{
      const [rows,series]=await Promise.all([
        Promise.all(visibleMachines.map(machine=>api.get('/ml/analysis/'+encodeURIComponent(machine.id)+'?tariff='+encodeURIComponent(tariff||8.0)).then(data=>[machine.id,data]).catch(e=>[machine.id,{status:'unavailable',message:e.message||'Could not load model result'}]))),
        analyticsService.series(visibleMachines,{rg:'Today',from:'',to:''}),
      ]);
      setAnalyses(Object.fromEntries(rows));setAnalysisSeries(series);setAnalysedAt(new Date());
    }catch(e){setError(e.message||'Could not analyse the latest meter readings')}
    finally{setAnalysisBusy(false)}
  };

  if(!visibleMachines.length)return <EmptyState>No machines are assigned to this account yet. Ask an admin to assign a machine before analysing readings.</EmptyState>;
  const x=visibleMachines.filter(m=>(recs[m.id]||[]).length);
  return <>
    <div className="row sb" style={{marginBottom:12}}><h3 style={{margin:0}}>Trained energy and anomaly model</h3><div className="row"><Pill>{LIVE?'VoltEdge ML model':'Rule-based'+(import.meta.env.VITE_USE_MOCK!=='false'?' (simulated)':'')}</Pill><button className="p" onClick={analyseNow} disabled={analysisBusy}>{analysisBusy?'Analysing…':'Analyse now'}</button></div></div>
    {error&&<div className="err" role="alert">{error}</div>}
    {analysisSeries&&<Card wide title="📈 Meter readings collected today" badge={analysedAt?`Updated ${analysedAt.toLocaleTimeString()}`:null}><p className="mut">Hourly energy calculated from readings received through the demo meter or connected IoT devices.</p>{analysisSeries.per.map(item=><div key={item.m.id} style={{marginBottom:14}}><h4 style={{margin:'8px 0'}}>{item.m.n}</h4><LineChart values={item.s.map(point=>point.e)} labels={item.s.map(point=>point.l)} unit=" kWh"/></div>)}</Card>}
    {LIVE&&visibleMachines.map(machine=><MLCard key={machine.id} machine={machine} assets={assets} analysis={analyses[machine.id]} draft={drafts[machine.id]} saving={saving===machine.id} canConfigure={user?.role==='admin'} onMappingChange={(id,value)=>setDrafts(previous=>({...previous,[id]:value}))} onSaveMapping={saveMapping}/>) }
    {LIVE&&<p className="mut">The anomaly model needs 97 consecutive completed 15-minute windows (about 24 hours) for its lag features. It shows “Building history” until enough telemetry has accumulated.</p>}
    <div className="row sb" style={{margin:'18px 0 12px'}}><h3 style={{margin:0}}>Why VoltEdge suggests each action</h3><Pill>{LIVE?'ML-backed anomalies':'Rule-based'+(import.meta.env.VITE_USE_MOCK!=='false'?' (simulated)':'')}</Pill></div>
    {x.length?x.map(m=><div key={m.id}><h3>{m.n}</h3><FlowStrip m={m}/><div className="grid">{recs[m.id].map(r=><RecCard key={r.rid} m={m} r={r} detail/>)}</div></div>):<EmptyState>{LIVE?'No trained-model anomalies are ready for display. Map each machine to its matching trained asset and allow sufficient telemetry history to accumulate.':'All machines are within normal range.'}</EmptyState>}
  </>;
}
