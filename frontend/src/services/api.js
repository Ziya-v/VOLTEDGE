export const MOCK=import.meta.env.VITE_USE_MOCK!=='false';
export const AUTH_MOCK=import.meta.env.VITE_USE_LIVE_AUTH!=='true';
const BASE=import.meta.env.VITE_API_URL||'/api';
async function req(method,path,body){const tok=localStorage.getItem('ve.token');
const r=await fetch(BASE+path,{method,headers:{'Content-Type':'application/json',...(tok?{Authorization:'Bearer '+tok}:{})},body:body?JSON.stringify(body):undefined});
const j=await r.json().catch(()=>({}));if(!r.ok)throw Object.assign(new Error(j.error||j.detail||r.statusText),{code:j.code,status:r.status});return j}
export const api={get:p=>req('GET',p),post:(p,b)=>req('POST',p,b),patch:(p,b)=>req('PATCH',p,b),delete:p=>req('DELETE',p)};

