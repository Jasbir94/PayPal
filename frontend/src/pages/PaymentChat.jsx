import React,{useEffect,useRef,useState} from 'react';
import {api} from '../services/api.js';

const SESSION_KEY='app-shield-chat-session';
const TOKEN_KEY='app-shield-demo-token';
const PROFILE_KEY='app-shield-demo-profile';
const OPTIONS=['Make Payment','Check Balance','Transaction Details'];
const money=value=>`₹${Number(value||0).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const when=value=>value?new Date(value).toLocaleString():'';

export default function PaymentChat(){
  const [session,setSession]=useState(localStorage.getItem(SESSION_KEY)||''),[data,setData]=useState(null),[messages,setMessages]=useState([]),[input,setInput]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [token,setToken]=useState(''),[profiles,setProfiles]=useState([]),[accountAlias,setAccountAlias]=useState(localStorage.getItem(PROFILE_KEY)||'U101'),[authReady,setAuthReady]=useState(false);
  const bottom=useRef(null);
  const pendingRequest=useRef(null);
  useEffect(()=>{let active=true;(async()=>{try{const result=await api.bankingProfiles();if(!active)return;setProfiles(result.profiles||[]);const saved=localStorage.getItem(TOKEN_KEY);if(saved){try{const current=await api.bankingSession(saved);if(active){setToken(saved);setAccountAlias(current.account.alias);setAuthReady(true);return}}catch{localStorage.removeItem(TOKEN_KEY)}}const login=await api.bankingDemoSession(accountAlias);if(active){setToken(login.access_token);setAccountAlias(login.account.alias);localStorage.setItem(TOKEN_KEY,login.access_token);localStorage.setItem(PROFILE_KEY,login.account.alias);setAuthReady(true)}}catch(e){if(active){setError(e.message);setAuthReady(true)}}})();return()=>{active=false}},[]);
  useEffect(()=>{if(!session||!token)return;let active=true;api.chatSession(session,token).then(value=>{if(active){setData(value);setMessages(value.messages||[])}}).catch(()=>{if(active){localStorage.removeItem(SESSION_KEY);setSession('')}});return()=>{active=false}},[session,token]);
  useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth'});},[messages,busy,data?.transactions,data?.balance]);

  function applyResult(result){setData(result);setMessages(result.messages||[]);if(result.session_id&&!session){setSession(result.session_id);localStorage.setItem(SESSION_KEY,result.session_id)}}
  async function send(value=input){const text=String(value||'').trim();if(!text||busy)return;if(!token){setError('The simulated account session is unavailable. Please try again.');return}const scope=session?`message:${session}`:'start';const previous=pendingRequest.current;const requestKey=previous&&previous.scope===scope&&previous.text===text?previous.key:(globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(16).slice(2)}`);pendingRequest.current={scope,text,key:requestKey};setInput('');setBusy(true);setError('');try{const result=session?await api.chatMessage(session,text,token,requestKey):await api.chatStart(text,token,requestKey);pendingRequest.current=null;applyResult(result)}catch(e){setError(e.message)}finally{setBusy(false)}}
  async function act(action){if(!session||!token||busy)return;setBusy(true);setError('');try{applyResult(await api.chatAction(session,action,token))}catch(e){setError(e.message)}finally{setBusy(false)}}
  async function switchProfile(alias){if(alias===accountAlias||busy)return;setBusy(true);setError('');try{if(session&&data?.payment&&!['SIMULATED_COMPLETED','CANCELLED','ERROR','SIMULATED_HELD'].includes(data.payment.state)){await api.chatAction(session,'cancel',token)}const login=await api.bankingDemoSession(alias);localStorage.setItem(TOKEN_KEY,login.access_token);localStorage.setItem(PROFILE_KEY,alias);localStorage.removeItem(SESSION_KEY);setToken(login.access_token);setAccountAlias(alias);setSession('');setData(null);setMessages([]);setInput('')}catch(e){setError(e.message)}finally{setBusy(false)}}

  const payment=data?.payment;
  const mainOptions=data?.main_options?.length?data.main_options:!messages.length?OPTIONS:[];
  const showComposer=true;
  return <div className="app-shell shieldpay-shell chat-shell"><main className="chat-page">
    <header className="chat-brand"><a href="/" aria-label="APP Shield home"><span className="chat-brand-mark" aria-hidden="true">S</span><span><strong>APP Shield</strong><small>Payment protection · Demo</small></span></a><label className="chat-account-picker">Demo account<select value={accountAlias} onChange={event=>switchProfile(event.target.value)} disabled={!authReady||busy}>{profiles.map(profile=><option key={profile.alias} value={profile.alias}>{profile.display_name}</option>)}</select></label></header>
    <section className="chat-heading"><h1>How can I help you today?</h1><p>Make a simulated payment, check your balance, or view transactions.</p></section>
    <section className="chat-window" aria-label="APP Shield conversation"><div className="chat-transcript" aria-live="polite">
      {!messages.length&&<ChatBubble role="assistant" text="Hello! How can I help you today?"/>}
      {messages.filter(item=>item.text).map((item,index)=><ChatBubble key={`${index}-${item.role}`} role={item.role} text={item.text}/>)}
      {busy&&<div className="chat-typing" role="status"><span/><span/><span/> Checking…</div>}
      <div ref={bottom}/>
    </div>
    {error&&<div className="error-banner chat-error" role="alert"><strong>Request not completed.</strong><span>{error}</span><button onClick={()=>setError('')} aria-label="Dismiss error">×</button></div>}
    {data?.recipient_options?.length>0&&<div className="chat-quick-replies" aria-label="Recipient choices">{data.recipient_options.map(option=><button key={option.value} disabled={busy} onClick={()=>send(option.value)}>{option.label}</button>)}</div>}
    {data?.quick_replies?.length>0&&<div className="chat-quick-replies" aria-label="Quick replies">{data.quick_replies.map(reply=><button key={reply} disabled={busy} onClick={()=>send(reply)}>{reply}</button>)}</div>}
    {mainOptions.length>0&&<div className="chat-main-options" aria-label="Main options">{mainOptions.map(option=><button key={option} disabled={busy||!authReady} onClick={()=>send(option)}>{option}</button>)}</div>}
    {data?.balance&&<BalanceCard balance={data.balance}/>}
    {Array.isArray(data?.transactions)&&<TransactionList rows={data.transactions} viewMore={data.view_more} onSelect={id=>send(`Show transaction details for ${id}`)} onMore={()=>send('View more transactions')}/>}
    {data?.transaction_detail&&<TransactionDetail transaction={data.transaction_detail}/>}
    {payment&&<PaymentReview payment={payment} actions={data.available_actions||[]} onAction={act} busy={busy}/>}
    {data?.knowledge?.length>0&&<details className="chat-guidance"><summary>Learn why</summary>{data.knowledge.map((item,index)=><article key={`${item.title}-${index}`}><strong>{item.title}</strong><small>{item.source}{item.publication_date?` · ${item.publication_date}`:''}</small><p>{item.excerpt}</p>{item.url&&<a href={item.url} target="_blank" rel="noreferrer">Read source ↗</a>}</article>)}</details>}
    {showComposer&&<form className="chat-composer" onSubmit={event=>{event.preventDefault();send()}}><label className="visually-hidden" htmlFor="chat-message">Message APP Shield</label><textarea id="chat-message" rows="1" maxLength="1000" value={input} onChange={event=>setInput(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();event.currentTarget.form?.requestSubmit()}}} placeholder="Type a message…" disabled={busy||!authReady}/><button className="button button-primary" disabled={busy||!authReady||!input.trim()} aria-label="Send message">{busy?'Checking…':'Send'}</button><small>Press Enter to send · Shift+Enter for a new line</small></form>}
    </section>
    <p className="chat-demo-note">Simulated accounts and payments · No real money moves</p>
  </main></div>;
}

function ChatBubble({role,text}){return <div className={`chat-row chat-row-${role}`}><div className="chat-bubble"><p>{text}</p></div></div>}
function BalanceCard({balance}){return <section className="chat-data-card" aria-label="Account balance"><small>Available balance</small><strong>{money(balance.available_balance)}</strong>{balance.held_balance>0&&<span>Held: {money(balance.held_balance)}</span>}</section>}
function TransactionList({rows,viewMore,onSelect,onMore}){return <section className="chat-data-card chat-transactions" aria-label="Recent transactions"><strong>Recent transactions</strong>{!rows.length?<p>No matching transactions yet.</p>:rows.map(row=><button className="chat-transaction-row" key={row.transaction_id} onClick={()=>onSelect(row.transaction_id)}><span className={row.direction==='DEBIT'?'chat-debit':'chat-credit'}>{row.direction==='DEBIT'?'−':'+'} {money(row.amount)}</span><span><b>{row.direction==='DEBIT'?'Paid to':'Received from'} {row.counterparty}</b><small>{when(row.created_at)} · {row.status}</small></span></button>)}{viewMore&&<button className="chat-inline-action" onClick={onMore}>View more</button>}</section>}
function TransactionDetail({transaction}){return <section className="chat-data-card chat-transaction-detail"><strong>Transaction details</strong><dl><div><dt>Transaction ID</dt><dd>{transaction.transaction_id}</dd></div><div><dt>Amount</dt><dd>{transaction.direction==='DEBIT'?'−':'+'} {money(transaction.amount)}</dd></div><div><dt>Direction</dt><dd>{transaction.direction==='DEBIT'?'Debit':'Credit'}</dd></div><div><dt>Sender</dt><dd>{transaction.sender}</dd></div><div><dt>Recipient</dt><dd>{transaction.recipient}</dd></div><div><dt>Date</dt><dd>{when(transaction.created_at)}</dd></div><div><dt>Status</dt><dd>{transaction.status}</dd></div>{transaction.purpose&&<div><dt>Purpose</dt><dd>{transaction.purpose}</dd></div>}</dl></section>}
function PaymentReview({payment,actions,onAction,busy}){
  const state=payment.state;
  const status=({READY:'Ready to review',WARNING:'Please check this payment',VERIFICATION_REQUIRED:'Verify before continuing',SIMULATED_HELD:'This payment is paused',SIMULATED_COMPLETED:'Completed',CANCELLED:'Cancelled',ERROR:'Failed'})[state]||'Payment review';
  const positive=(payment.protective_reasons||[]).filter(Boolean).slice(0,2),receipt=payment.receipt;
  return <section className={`chat-payment-card chat-payment-${state.toLowerCase()}`} aria-label={state==='SIMULATED_COMPLETED'?'Payment receipt':'Payment review'}><div className="chat-review-top"><div><span className="chat-review-label">{state==='SIMULATED_COMPLETED'?'Payment receipt':'Payment review'}</span><h2>{money(payment.amount)} <span>to</span> {payment.recipient?.display_name}</h2></div><strong className="chat-status">{status}</strong></div><p className="chat-recipient-note">Recipient ID: {payment.recipient?.account_id||'Unavailable'}</p>{payment.decision&&state!=='SIMULATED_COMPLETED'&&<p className="chat-intervention-copy">{payment.intervention?.message||'Review the recipient and payment details before continuing.'}</p>}{receipt&&<dl className="chat-receipt-details"><div><dt>Transaction ID</dt><dd>{receipt.transaction_id}</dd></div><div><dt>Status</dt><dd>{receipt.status}</dd></div><div><dt>Settlement</dt><dd>{receipt.settlement_type==='INTERNAL_TRANSFER'?'Internal transfer':'Simulated external settlement'}</dd></div></dl>}{positive.length>0&&<div className="chat-protective"><strong>Helpful context</strong><ul>{positive.map((reason,index)=><li key={`${reason}-${index}`}>{reason}</li>)}</ul></div>}<div className="chat-payment-actions">{actions.includes('cancel')&&<button className="button button-quiet" disabled={busy} onClick={()=>onAction('cancel')}>Cancel</button>}{actions.includes('verify')&&<button className="button button-secondary" disabled={busy} onClick={()=>onAction('verify')}>I independently verified</button>}{actions.includes('confirm')&&<button className="button button-primary" disabled={busy} onClick={()=>onAction('confirm')}>Confirm &amp; Send</button>}</div>{state!=='SIMULATED_COMPLETED'&&<small>APP Shield’s backend controls this review. No real money moves.</small>}</section>
}
