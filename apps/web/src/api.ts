export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  const response=await fetch(`/api${path}`,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  if(!response.ok){const data=await response.json().catch(()=>({detail:'Request failed'}));throw new Error(typeof data.detail==='string'?data.detail:'Please check the form and try again.');}
  return response.json();
}
export const post=<T>(path:string, body:unknown={})=>api<T>(path,{method:'POST',body:JSON.stringify(body)});
export const statusLabel=(value:string)=>({new:'New',queued:'Queued',running:'Investigating',investigating:'Investigating',awaiting_approval:'Needs review',resume_queued:'Processing',resolved:'Resolved',escalated:'Escalated',needs_information:'Needs information',rejected:'Rejected',failed:'Failed'}[value]||value);
export const money=(cents:number)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents/100);
