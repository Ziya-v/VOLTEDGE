// MOCK ONLY: seeded demo series (same date range -> same numbers). Replace with GET /api/analytics.
const hash=x=>{let h=2166136261;for(const c of x)h=Math.imul(h^c.charCodeAt(0),16777619);return h>>>0};
const rnd=a=>()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296};
const day0=d=>{d=new Date(d);d.setHours(0,0,0,0);return d},iso=d=>new Date(d-d.getTimezoneOffset()*6e4).toISOString().slice(0,10);
const when=(w,i)=>{const d=new Date(w.start);w.u==='h'?d.setHours(i):w.u==='m'?d.setMonth(d.getMonth()+i):d.setDate(d.getDate()+i);return d};
const lab=(d,u)=>u==='h'?d.getHours()+'h':u==='m'?d.toLocaleString('en',{month:'short'}):d.getDate()+'/'+(d.getMonth()+1);
const mSeries=(m,w)=>Array.from({length:w.n},(_,i)=>{const d=when(w,i),r=rnd(hash(m.id+d.toISOString())),a=r(),b=r(),sc=w.u==='h'?1:w.u==='m'?600:20,kwu=m.kw0/m.u*(.92+b*.16);
return{l:lab(d,w.u),e:m.kw0*.7*sc*(.85+a*.3)*(m.id==='M4'?1+i/w.n*.15:1),kwu,eff:kwu>0?Math.min(99,m.bK/kwu*88):0}});
const total=(w,ms)=>{const x=ms.map(m=>mSeries(m,w));return Array.from({length:w.n},(_,i)=>({l:x[0][i].l,e:x.reduce((a,s)=>a+s[i].e,0),eff:x.reduce((a,s)=>a+s[i].eff,0)/x.length}))};
const agg=s=>({e:s.reduce((a,b)=>a+b.e,0),kwu:s.reduce((a,b)=>a+b.kwu,0)/s.length,eff:s.reduce((a,b)=>a+b.eff,0)/s.length});

export function win({rg,from,to}){const e=day0(new Date());let s;
if(rg==='Today')return{start:e,n:24,u:'h'};
if(rg==='7D'){s=new Date(e);s.setDate(s.getDate()-6);return{start:s,n:7,u:'d'}}
if(rg==='30D'){s=new Date(e);s.setDate(s.getDate()-29);return{start:s,n:30,u:'d'}}
if(rg==='1Y')return{start:new Date(e.getFullYear(),e.getMonth()-11,1),n:12,u:'m'};
const a=day0(from||e),b=day0(to||e),n=Math.min(120,Math.max(1,Math.round((b-a)/864e5)+1));return n===1?{start:a,n:24,u:'h'}:{start:a,n,u:'d'}}
export const sel=(machines,id)=>id==='all'?machines:machines.filter(m=>m.id===id);
export {hash,rnd,day0,iso,when,lab,mSeries,total,agg};

