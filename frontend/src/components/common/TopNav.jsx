import React from 'react';

export default function TopNav({ active='home', analyst=false, research=false, onReset }) {
  return <header className="topbar shieldpay-topbar">
    <a className="wordmark shieldpay-wordmark" href="/" aria-label="ShieldPay home">
      <span className="brand-mini">S</span><span>ShieldPay <small>POWERED BY APP SHIELD</small></span>
    </a>
    <nav className="topbar-right" aria-label="Main navigation">
      <span className="simulation-badge"><i/> DEMO ENVIRONMENT</span>
      <a className={`nav-link ${active==='transactions'?'nav-active':''}`} href="/transactions">Transactions</a>
      <a className={`nav-link ${active==='demo'?'nav-active':''}`} href="/demo">Demo scenarios</a>
      {analyst?<a className="nav-link" href="/">Customer view</a>:<a className="nav-link" href="/analyst">Analyst view</a>}
      {research&&<a className="nav-link" href="/analyst">Analyst console</a>}
      {onReset&&<button className="reset-button" onClick={onReset}>Reset demo</button>}
    </nav>
  </header>;
}
