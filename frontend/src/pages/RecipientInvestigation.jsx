import React,{useEffect,useState} from 'react';
import TopNav from '../components/common/TopNav.jsx';
import AppFooter from '../components/common/AppFooter.jsx';
import RecipientNetwork from '../components/analyst/RecipientNetwork.jsx';
import {api} from '../services/api.js';

export default function RecipientInvestigation(){
  const [accounts,setAccounts]=useState([]),[accountId,setAccountId]=useState(''),[result,setResult]=useState(null),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let active=true;api.accounts().then(value=>{if(active){setAccounts(value.recipients||[]);setLoading(false)}}).catch(e=>{if(active){setError(e.message);setLoading(false)}});return()=>{active=false}},[]);
  async function investigate(event){event.preventDefault();if(!accountId)return;setBusy(true);setError('');setResult(null);try{setResult(await api.recipientNetwork(accountId))}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <div className="app-shell analyst-shell"><TopNav active="analyst" analyst/><main className="customer-container page-container"><section className="page-title-row"><div><div className="eyebrow">RECIPIENT INVESTIGATION</div><h1>Explore a recipient’s network</h1><p>Inspect observed synthetic transfer connections without creating a payment attempt.</p></div><a className="button button-secondary" href="/analyst">Back to analyst cases</a></section>
    <section className="card recipient-lookup"><form onSubmit={investigate}><label className="field"><span>Recipient account ID</span><input list="known-recipients" value={accountId} onChange={event=>setAccountId(event.target.value.trim())} placeholder="Choose a demo recipient or enter an account ID" disabled={loading||busy}/><datalist id="known-recipients">{accounts.map(item=><option key={`${item.alias}-${item.account_id}`} value={item.account_id}>{item.display_name} · {item.alias}</option>)}</datalist></label><button className="button button-primary" disabled={!accountId||busy}>{busy?'Loading network…':'Investigate recipient'}</button></form><p className="research-note">Network edges are historical synthetic transfers in the available graph window. Connections alone do not establish intent.</p></section>
    {loading&&<p role="status" className="card">Loading recipient catalog…</p>}{error&&<p role="alert" className="inline-error">{error}</p>}{result&&<RecipientNetwork data={result} assessment={null}/>}
  </main><AppFooter/></div>
}
