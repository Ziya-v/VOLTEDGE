// MOCK ONLY. Real machines come from GET /api/machines.
export const MACHINES=[
{id:'M1',n:'CNC-01',ty:'Machining',cat:'Production',loc:'Bay A',kw:14,rt:22,u:40,con:'stoppable',pf:.93,temp:48,bT:50,bK:.34,idle:true},
{id:'M2',n:'Compressor-01',ty:'Compressor',cat:'Utility',loc:'Utility room',kw:44,rt:55,u:110,con:'continuous_operation_required',pf:.89,temp:78,bT:70,bK:.36},
{id:'M3',n:'Pump-01',ty:'Pump',cat:'Utility',loc:'Utility room',kw:17,rt:22,u:60,con:'continuous_operation_required',pf:.94,temp:52,bT:55,bK:.27},
{id:'M4',n:'Chiller-01',ty:'Chiller',cat:'Utility',loc:'Roof',kw:36,rt:50,u:80,con:'continuous_operation_required',pf:.91,temp:61,bT:60,bK:.40},
{id:'M5',n:'Motor-01',ty:'Motor',cat:'Production',loc:'Bay B',kw:11,rt:15,u:35,con:'stoppable',pf:.95,temp:44,bT:55,bK:.30}];
MACHINES.forEach(m=>{m.kw0=m.kw});
