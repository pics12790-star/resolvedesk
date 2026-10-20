import type {Activity, Order, Product, Run, Ticket, User} from '../types';

export type Scenario = {id:string;label:string;subject:string;message:string;owner:string;source:string};
type Workflow = Scenario & {
  order: Order & {product_id?:string;stock?:number;currency?:string};
  state: Run['state']; investigation: Omit<Activity,'id'|'created'>[];
  receipt: Record<string,unknown>|null; status:string;
};
type DemoTicket = Ticket & {customer_id:string;scenario_id:string};
type DemoOrder = Order & {customer_id:string;product_id?:string};
type DemoRun = Run & {
  ticket_id:string;scenario_id:string;events:Activity[];started:number;
  phase:'investigate'|'execute'|'done';visible:number;duplicate:boolean;
};
type Workspace = {version:1;identity:string;tickets:DemoTicket[];orders:DemoOrder[];runs:DemoRun[];products:Product[]};
const KEY = 'resolvedesk.walkthrough.v1';
const STEP_MS = 550;
const identities: Record<string, User> = {
  reviewer:{id:'reviewer',name:'Jordan Smith',role:'reviewer',customer_id:null},
  maya:{id:'maya',name:'Maya Chen',role:'customer',customer_id:'C-1'},
  alex:{id:'alex',name:'Alex Rivera',role:'customer',customer_id:'C-2'},
  priya:{id:'priya',name:'Priya Kapoor',role:'customer',customer_id:'C-3'},
};
let workspace: Workspace;
let boot: Promise<void>|undefined;
let scenarios: Scenario[] = [];
const workflows = new Map<string, Promise<Workflow>>();

async function fixture<T>(path:string):Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error('Saved workflow could not be loaded. Please refresh and try again.');
  return response.json();
}
function workflow(id:string) {
  if (!scenarios.some(s=>s.id===id)) throw new Error('Choose one of the available enquiry workflows.');
  if (!workflows.has(id)) workflows.set(id,fixture<Workflow>(`/workflows/${id}.json`).catch(error=>{workflows.delete(id);throw error}));
  return workflows.get(id)!;
}
function persist() {
  // Private browsing or a full storage quota must not break the walkthrough.
  try {localStorage.setItem(KEY, JSON.stringify(workspace));} catch { /* Session remains usable in memory. */ }
}
function clone<T>(value:T):T {return structuredClone(value);}
function id(prefix:string) {return `${prefix}-${crypto.randomUUID().slice(0,8)}`;}
function user() {return identities[workspace.identity];}
function customer() {return user().role==='reviewer'?identities.maya:user();}
function reviewer() {if(user().role!=='reviewer') throw new Error('Reviewer access required');}
function ticketFor(tid:string) {
  const ticket = workspace.tickets.find(t=>t.id===tid);
  if (!ticket || (user().role!=='reviewer' && ticket.customer_id!==user().customer_id)) throw new Error('Ticket not found');
  return ticket;
}
function runFor(rid:string) {
  const run = workspace.runs.find(r=>r.id===rid);
  if (!run) throw new Error('Run not found');
  ticketFor(run.ticket_id);
  return run;
}
function publicRun(run:DemoRun):Run {return clone({id:run.id,status:run.status,error:run.error,state:run.state});}
function event(run:DemoRun,kind:string,message:string,data:Record<string,unknown>={}) {
  run.events.push({id:run.events.length+1,kind,message,data,created:Date.now()/1000});
}
function orderFor(ticket:DemoTicket) {return workspace.orders.find(o=>o.id===ticket.order_id)!;}
function bind<T>(value:T,template:Workflow,ticket:DemoTicket):T {
  const order = orderFor(ticket);
  function walk(item:unknown):unknown {
    if (typeof item==='string') {
      if (item===template.order.id) return order.id;
      if (item===template.order.product_id) return order.product_id;
      return item.replaceAll(template.order.product,order.product)
        .replaceAll(`$${(template.order.total_cents/100).toFixed(2)}`,`$${(order.total_cents/100).toFixed(2)}`);
    }
    if (Array.isArray(item)) return item.map(walk);
    if (item && typeof item==='object') return Object.fromEntries(Object.entries(item).map(([k,v])=>[
      k, ['amount_cents','total_cents'].includes(k) && typeof v==='number'?order.total_cents:walk(v),
    ]));
    return item;
  }
  return walk(value) as T;
}
async function ensure() {
  if (!boot) boot = (async()=>{
    scenarios = await fixture<Scenario[]>('/workflows/index.json');
    try {
      const saved = JSON.parse(localStorage.getItem(KEY)||'null');
      if (saved?.version===1 && identities[saved.identity] && Array.isArray(saved.tickets)
        && Array.isArray(saved.orders) && Array.isArray(saved.runs) && Array.isArray(saved.products)
        && saved.tickets.every((t:DemoTicket)=>scenarios.some(s=>s.id===t.scenario_id))) {
        workspace=saved;
        return;
      }
    } catch { /* Ignore unavailable storage or an outdated workspace. */ }
    const templates = await Promise.all(['replacement','delivery','refund-status'].map(workflow));
    workspace={version:1,identity:'reviewer',tickets:[],orders:[],runs:[],products:[
      {id:'P-1',name:'Studio headphones',description:'Over-ear headphones',price_cents:12900,currency:'USD',stock:8,unlimited:false},
      {id:'P-2',name:'Everyday backpack',description:'Everyday carry backpack',price_cents:7900,currency:'USD',stock:5,unlimited:false},
      {id:'P-3',name:'Desk lamp',description:'Adjustable desk lamp',price_cents:6400,currency:'USD',stock:4,unlimited:false},
      {id:'P-4',name:'USB-C cable',description:'USB-C accessory',price_cents:1900,currency:'USD',stock:1000000,unlimited:true},
    ]};
    templates.forEach((template,i)=>{
      const owner=identities[template.owner];
      workspace.orders.push({...clone(template.order),customer_id:owner.customer_id!});
      workspace.tickets.push({id:`T-${1001+i}`,customer_id:owner.customer_id!,customer_name:owner.name,
        subject:template.subject,message:template.message,order_id:template.order.id,status:'new',created:Date.now()/1000-i,
        scenario_id:template.id});
    });
    persist();
  })().catch(error=>{boot=undefined;throw error});
  await boot;
}
const advancing=new Map<string,Promise<void>>();
async function advance(run:DemoRun) {
  if(advancing.has(run.id)) return advancing.get(run.id);
  const task=advanceRun(run).finally(()=>advancing.delete(run.id));
  advancing.set(run.id,task);return task;
}
async function advanceRun(run:DemoRun) {
  if (run.phase==='done' || run.status==='awaiting_approval') return;
  const template=await workflow(run.scenario_id);
  const ticket=workspace.tickets.find(t=>t.id===run.ticket_id)!;
  const order=orderFor(ticket);
  if (run.phase==='execute') {
    if (Date.now()-run.started<1000) return;
    const existing=workspace.runs.find(r=>r.id!==run.id&&r.state.receipt?.order_id===order.id);
    if(existing) {
      run.state.receipt=clone(existing.state.receipt);
      run.state.proposal={action:'answer',explanation:'An approved remedy already exists for this order. No duplicate action was executed.',customer_response:'Your approved remedy is already recorded.',citations:run.state.proposal?.citations||[],order_id:order.id,amount_cents:null};
      event(run,'validation','Existing remedy found; duplicate action prevented');
      run.status=ticket.status='resolved';run.phase='done';persist();return;
    }
    const action=run.state.proposal!.action;
    // Local, simulated receipt; no payment or shipping service is contacted.
    const receipt={...bind(template.receipt||{},template,ticket),id:id('RCPT'),order_id:order.id,action,simulated:true};
    run.state.receipt=receipt;
    if (action==='replacement') order.replacement_id=receipt.id;
    if (action==='refund') order.refund_status='pending';
    run.state.tool_calls=(run.state.tool_calls||0)+2;
    event(run,'receipt','Approved action executed and verified',receipt);
    event(run,'complete','Investigation finished',{status:'resolved'});
    run.status=ticket.status='resolved';run.phase='done';persist();return;
  }
  const target=Math.min(template.investigation.length,Math.floor((Date.now()-run.started)/STEP_MS));
  let changed=false;
  while (run.visible<target) {
    const step=template.investigation[run.visible++];
    event(run,step.kind,step.message,bind(step.data,template,ticket));
    if(step.kind==='retrieve') run.state.policies=clone(template.state.policies);
    if(step.kind==='tool') {run.state.evidence=bind(template.state.evidence,template,ticket);run.state.tool_calls=(run.state.tool_calls||0)+1;}
    changed=true;
  }
  if (target===template.investigation.length) {
    run.state={...bind(template.state,template,ticket),tool_calls:run.state.tool_calls||0};
    run.duplicate=run.duplicate||!!order.replacement_id||workspace.runs.some(r=>r.id!==run.id&&r.state.receipt?.order_id===order.id);
    if(run.duplicate) {
      run.state.proposal={action:'answer',explanation:'An approved remedy already exists for this order. No second refund or replacement will be created.',
        customer_response:'Your approved remedy is already recorded. We will not create a duplicate.',citations:run.state.proposal?.citations||[],order_id:order.id,amount_cents:null};
      run.state.receipt=clone(workspace.runs.find(r=>r.state.receipt?.order_id===order.id)?.state.receipt);
      event(run,'validation','Existing remedy found; duplicate action prevented');
    }
    if (['replacement','refund'].includes(run.state.proposal!.action)) {
      run.status=ticket.status='awaiting_approval';
      event(run,'approval','Waiting for reviewer approval',{proposal_hash:`saved:${run.id}`});
    } else {
      run.status=ticket.status=run.duplicate?'resolved':template.status;
      event(run,'complete','Investigation finished',{status:run.status});run.phase='done';
    }
    changed=true;
  }
  if(changed) persist();
}
async function advanceAll() {await Promise.all(workspace.runs.map(advance));}

export async function demoApi<T>(path:string,options:RequestInit={}):Promise<T> {
  await ensure();await advanceAll();
  const method=options.method||'GET';
  const body=options.body?JSON.parse(String(options.body)):{};
  let result:unknown;
  if(path==='/health') result={status:'ok',agent_mode:'walkthrough',store:'browser-local',judge:'Saved historical evaluations'};
  else if(path==='/auth/me') result=user();
  else if(path==='/auth/demo' && method==='POST') {
    if(!identities[body.identity]) throw new Error('Choose an available demo identity');
    workspace.identity=body.identity;persist();result=user();
  } else if(path==='/walkthrough/scenarios') result=scenarios;
  else if(path==='/walkthrough/reset' && method==='POST') {
    // Reset only this browser's walkthrough, never the real backend.
    try {localStorage.removeItem(KEY)} catch { /* Storage may be disabled. */ }
    boot=undefined;await ensure();result={ok:true};
  } else if(path==='/products') result=workspace.products;
  else if(path==='/orders' && method==='POST') {
    const product=workspace.products.find(p=>p.id===body.product_id);
    if(!product || (!product.unlimited&&product.stock<1)) throw new Error('Product is unavailable');
    if(body.quantity!==1) throw new Error('Choose one product for this enquiry');
    const order:DemoOrder={id:id('ORD'),product_id:product.id,product:product.name,total_cents:product.price_cents,
      shipment_status:'delivered',refund_status:null,replacement_id:null,customer_id:customer().customer_id!};
    if(!product.unlimited) product.stock--;
    workspace.orders.push(order);persist();result=order;
  } else if(path==='/tickets' && method==='GET') {
    result=workspace.tickets.filter(t=>user().role==='reviewer'||t.customer_id===user().customer_id).sort((a,b)=>b.created-a.created);
  } else if(path==='/tickets' && method==='POST') {
    const template=await workflow(body.scenario_id);
    if(typeof body.subject!=='string'||body.subject.trim().length<3||body.subject.length>140||typeof body.message!=='string'||body.message.trim().length<5||body.message.length>4000) throw new Error('Enter a subject and message for your enquiry');
    const owner=customer();
    let order=body.order_id?workspace.orders.find(o=>o.id===body.order_id&&o.customer_id===owner.customer_id):undefined;
    if(body.order_id&&!order) throw new Error('Use an order belonging to this customer, or leave the field empty for a new sample order.');
    if(order&&workspace.tickets.some(t=>t.order_id===order!.id&&t.scenario_id!==template.id)) throw new Error('This order belongs to a different saved workflow. Leave the order number empty to create the matching sample order.');
    if(order&&!workspace.tickets.some(t=>t.order_id===order!.id)) {
      order.shipment_status=template.order.shipment_status;order.refund_status=template.order.refund_status;
    }
    if(!order) {order={...clone(template.order),id:id('ORD'),customer_id:owner.customer_id!};workspace.orders.push(order);}
    const ticket:DemoTicket={id:id('T'),subject:body.subject.trim(),message:body.message.trim(),order_id:order.id,
      customer_name:owner.name,customer_id:owner.customer_id!,scenario_id:template.id,status:'new',created:Date.now()/1000};
    workspace.tickets.push(ticket);persist();result=ticket;
  } else if(/^\/tickets\/[^/]+$/.test(path)) {
    const ticket=ticketFor(path.split('/')[2]);
    result={...ticket,order:orderFor(ticket),runs:workspace.runs.filter(r=>r.ticket_id===ticket.id).slice().reverse().map(publicRun)};
  } else if(/^\/tickets\/[^/]+\/runs$/.test(path)&&method==='POST') {
    const ticket=ticketFor(path.split('/')[2]);
    if(workspace.runs.some(r=>r.ticket_id===ticket.id&&['queued','running','awaiting_approval','resume_queued'].includes(r.status))) throw new Error('This enquiry already has an active investigation');
    const order=orderFor(ticket);
    const run:DemoRun={id:id('R'),ticket_id:ticket.id,scenario_id:ticket.scenario_id,status:'running',error:null,state:{},
      events:[],started:Date.now(),visible:0,phase:'investigate',duplicate:!!order.replacement_id||workspace.runs.some(r=>r.state.receipt?.order_id===order.id)};
    workspace.runs.push(run);ticket.status='running';persist();result={id:run.id};
  } else if(/^\/runs\/[^/]+\/approval$/.test(path)&&method==='POST') {
    reviewer();const run=runFor(path.split('/')[2]);
    if(run.status!=='awaiting_approval'||body.proposal_hash!==`saved:${run.id}`||typeof body.approve!=='boolean') throw new Error('This proposal is no longer waiting for your decision');
    const ticket=ticketFor(run.ticket_id);
    if(body.approve) {
      // Re-check all runs for this order before simulating a mutation.
      if(workspace.runs.some(r=>r.id!==run.id&&r.state.receipt?.order_id===ticket.order_id)) throw new Error('An approved remedy already exists for this order');
      if(workspace.runs.some(r=>r.id!==run.id&&r.phase==='execute'&&workspace.tickets.find(t=>t.id===r.ticket_id)?.order_id===ticket.order_id)) throw new Error('Another approved action is processing for this order. Wait for its receipt before continuing.');
      run.phase='execute';run.started=Date.now();run.status=ticket.status='resume_queued';
      event(run,'approval','Reviewer approved the proposal');
    } else {
      run.status=ticket.status='rejected';run.phase='done';
      event(run,'approval','Reviewer rejected the proposal');event(run,'complete','Investigation finished',{status:'rejected'});
    }
    persist();result={approval_id:id('A')};
  } else if(/^\/runs\/[^/]+\/audit$/.test(path)) result=runFor(path.split('/')[2]).events;
  else if(/^\/runs\/[^/]+$/.test(path)) result=publicRun(runFor(path.split('/')[2]));
  else if(path==='/policies') result=await fixture('/policies.json');
  else if(path==='/evaluations') {reviewer();result=await fixture('/evaluations/index.json');}
  else if(/^\/evaluations\/[\w-]+$/.test(path)) {reviewer();result=await fixture(`/evaluations/${path.split('/')[2]}.json`);}
  else throw new Error('This action is not available in the saved-run walkthrough.');
  return clone(result) as T;
}

export function subscribeDemoRun(rid:string,onEvent:(event:Activity)=>void,onStatus:(status:string)=>void,onError:()=>void) {
  let closed=false,checking=false,last=0;
  async function tick() {
    if(closed||checking) return;
    checking=true;
    try {
      await ensure();const run=runFor(rid);await advance(run);
      if(closed)return;
      for(const entry of run.events) if(entry.id>last){onEvent(clone(entry));last=entry.id;}
      onStatus(run.status);
    } catch {if(!closed)onError();} finally {checking=false;}
  }
  const timer=window.setInterval(()=>void tick(),250);
  void tick();
  return ()=>{closed=true;window.clearInterval(timer);};
}
