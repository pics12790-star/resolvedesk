import {useEffect,useRef,useState} from 'react';
import {ShoppingBag,X,Plus} from 'lucide-react';
import {api,money,post} from './api';
import type {Order,Product,Ticket,User} from './types';
export function NewTicket({user,onClose,onCreated}:{user:User|null;onClose:()=>void;onCreated:(t:Ticket)=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 const [subject,setSubject]=useState(''),[message,setMessage]=useState(''),[order,setOrder]=useState(''),[busy,setBusy]=useState(false),[buying,setBuying]=useState(''),[error,setError]=useState(''),[products,setProducts]=useState<Product[]>([]),[createdOrder,setCreatedOrder]=useState<Order|null>(null);
 useEffect(()=>{dialog.current?.showModal();api<Product[]>('/products').then(setProducts).catch(()=>{});},[]);
 async function buy(productId:string){
  setBuying(productId);setError('');
  try{const result=await post<Order>('/orders',{product_id:productId,quantity:1});setCreatedOrder(result);setOrder(result.id);}
  catch(e){setError((e as Error).message)}
  finally{setBuying('')}
 }
 return <dialog ref={dialog} onCancel={onClose}><form onSubmit={async e=>{e.preventDefault();setBusy(true);try{onCreated(await post<Ticket>('/tickets',{subject,message,order_id:order||null}));}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}><div className="modal-header"><h2>New support ticket</h2><button type="button" className="icon-button" aria-label="Close new ticket" onClick={onClose}><X/></button></div><p className="muted">Creating a ticket for {user?.role==='reviewer'?'Maya Chen':user?.name} in the demo store.</p><label>Subject<input autoFocus required minLength={3} maxLength={140} value={subject} onChange={e=>setSubject(e.target.value)} placeholder="What do you need help with?"/></label><label>Order number<input maxLength={50} value={order} onChange={e=>setOrder(e.target.value)} placeholder="ORD-1001"/></label><div className="order-helper" data-tour="buy-demo-product"><div><strong>Need an order number?</strong><p>Buy a seeded demo product, then come back here and raise the ticket with the generated order.</p></div>{createdOrder&&<div className="created-order">Created <button type="button" onClick={()=>setOrder(createdOrder.id)}>{createdOrder.id}</button></div>}<div className="product-picker">{products.slice(0,4).map(p=><button key={p.id} type="button" className="product-choice" disabled={!!buying||(!p.unlimited&&p.stock<1)} onClick={()=>buy(p.id)}><ShoppingBag size={17}/><span><strong>{p.name}</strong><small>{money(p.price_cents)} · {p.unlimited?'unlimited stock':`${p.stock} in stock`}</small></span>{buying===p.id?'Buying…':'Buy'}</button>)}</div></div><label>Message<textarea required minLength={5} maxLength={4000} rows={5} value={message} onChange={e=>setMessage(e.target.value)} placeholder="Describe what happened…"/></label>{error&&<p role="alert" className="error-banner">{error}</p>}<div className="modal-actions"><button type="button" className="secondary" onClick={onClose}>Cancel</button><button className="primary" disabled={busy}><Plus size={16}/>{busy?'Creating…':'Create ticket'}</button></div></form></dialog>
}
