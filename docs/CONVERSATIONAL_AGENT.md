# APP Shield AI payment conversation

The `/` and `/send` routes open the same customer chat. It starts with **Make Payment**, **Check Balance**, and **Transaction Details**, and also routes typed requests. The server owns chat sessions and structured follow-up questions; the existing `PaymentSimulator`, APP Shield model stack, fusion, intervention policy, and payment state machine continue to own assessment and allowed actions.

## Chat and payment lifecycle

`POST /api/v1/chat/sessions` begins an account-bound session from a short natural-language request. It requires a bearer token returned by `POST /api/v1/banking/demo-sessions`. Amounts are parsed from rupees, INR, `Rs`, or a bare number next to a payment verb. Recipients resolve only to entries in the backend synthetic catalog. Unknown recipients are not invented or verified.

`POST /api/v1/chat/sessions/{session_id}/messages` stores the bounded session turn, answers backend-selected context questions, records claims as unverified with `user_report` provenance, and runs the existing payment assessment. Balance, transaction list, payee/date/direction totals, and transaction-detail requests read from the configured SQL wallet store. `GET /api/v1/chat/sessions/{session_id}` restores the in-memory chat for up to 30 minutes. `POST /api/v1/chat/sessions/{session_id}/actions/{cancel|verify|confirm}` delegates to the simulator; confirmation is a separate explicit action, and repeating confirmation in this chat returns the original receipt.

Sessions have per-process isolation, a 30-minute idle expiry, a 500-session cap, and no durable chat transcript store. The bearer token is bound to one synthetic account and chat-session access is scoped to that account. The local demo profile picker does not prove real identity; do not expose this service as production banking authentication. Sensitive credential patterns are rejected before they enter the session. Chat audit events record question IDs and evidence field names, not raw chat text.

## Simulated account and ledger APIs

`POST /api/v1/banking/demo-sessions` issues an opaque bearer session for one demo profile. `GET /api/v1/banking/balance`, `GET /api/v1/banking/transactions`, and `GET /api/v1/banking/transactions/{transaction_id}` require that bearer session and only return its account's records. The account picker selects U101 (₹10,000), U102 (₹2,000), or U103 (₹10,000) by default. With `DATABASE_URL`, balances and transaction records are stored in PostgreSQL; without it, local state is transient. See [the ledger design and limits](BANKING_DEMO.md).

The internal R207 profile maps to U102. A successful confirmed internal payment debits the sender and credits the recipient in one atomic SQL transaction and writes one payment row plus a debit/credit pair. Other recipients are external simulated settlements: the sender's ledger records the debit, while no recipient wallet is fabricated. Insufficient funds are checked before review and rechecked atomically at settlement.

## Adaptive question selection

`backend/app/conversation/adaptive_question_engine.py` uses a documented, deterministic relevance ordering based on payment purpose and the backend passive risk level. It asks at most one primary question by default. It does not claim an expected-information-gain score; that field remains null. Unknown recipient cases ask who initiated the payment. Investment and job cases ask about return promises and advance fees respectively. The existing payment form remains available at `/send/form` and still uses the same server-provided question contract.

## Local RAG

`backend/app/rag/knowledge_store.py` chunks a small reviewed local corpus, validates official source hosts against an allowlist, hashes each chunk, and ranks candidates with a lightweight lexical/BM25-style hybrid score. Category filters and a relevance floor reject unrelated results. Returned citations include document/chunk IDs, source, category, version, publication/retrieval dates, language, trust level, and a content hash. Retrieved documents can explain a concern but cannot change payment policy or actions.

The reviewed external references currently include:

- RBI's [caution against fraudulent activities in its name](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=58595), dated 29 August 2024.
- National Cyber Crime Reporting Portal's [financial fraud safety brochure](https://cybercrime.gov.in/pdf/Financial%20Fraud%20Brochures%20final.pdf).
- RBI's [investor education material on risk and returns](https://www.rbi.org.in/FinancialEducation/content/I%20Can%20Do_RBI.pdf); the source publication date is not asserted when unavailable.

The remaining documents are clearly labelled APP Shield internal demo guidance, not external authority. Retrieval happens locally; no customer conversation is sent to a hosted model or vector provider.

## LLM and language limitations

No LLM is configured. Replies use short templates based on the actual backend decision and retrieved source excerpts. This is a local retrieval-grounded conversational assistant, not a generative LLM agent. English and a small set of Hinglish payment verbs/amount patterns are supported by deterministic parsing; broader multilingual understanding, confidence-scored entity resolution, and ambiguous-name ranking need a measured language model or reviewed parser before production use.

The demo has synthetic accounts only, does not verify a real recipient, has no live payment gateway, and never moves real money. `GET /api/v1/chat/health` reports retriever/session availability and whether an LLM is configured.
