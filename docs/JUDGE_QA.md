# Judge Q&A

**What is new here?** The project explores explicit fusion of transaction, recipient/network, and user-manipulation context for pre-payment authorized-scam interventions. It does not claim to invent scam detection.

**Does this already exist at payment companies?** Payment companies use sophisticated fraud and scam controls, including pre-payment interventions. APP Shield is a research prototype and makes no claim about another company's systems.

**Why psychology signals?** Authority, fear, urgency, secrecy, reward, and scarcity may be visible in a scam request even when amount/device behavior looks ordinary. Those signals are evidence, not standalone proof of fraud.

**Where does conversation data come from?** It is optional user-provided context in this simulator, bounded and processed locally. The prototype does not ingest messages from a user's device or a payment platform.

**What if conversation is missing?** Transaction, recipient, and graph evidence can still be used; the system reports missingness and may lower confidence.

**How do you limit false positives?** Recipient history and protective evidence matter, high-risk alone does not queue every case, and intervention policy is conservative. The synthetic hard-negative payment holdout is not linked, so broad false-positive claims remain unmeasured.

**How do you prevent leakage?** Splits are chronological; repository history queries are strict-before timestamp; graph construction is bounded by payment time; future/equal-time fixtures are tested.

**How do you know it works?** Only synthetic evaluation currently exists. On 400 later synthetic rows, registered fusion recall was 0.485 at its frozen threshold; an independently fitted transaction-plus-recipient ablation achieved recall 0.636. There are 33 positive test cases, and no real-world claim follows.

**Why synthetic data?** It enables reproducible engineering and scenario demonstrations without exposing customer data. It is not representative evidence for deployment.

**Can this run in real time?** Local component timings are low in the simulator, but this has not been stress-tested at payment-platform scale or under real service constraints.

**How is privacy handled?** Inputs are bounded, credential patterns are rejected, logs use pseudonymous references, and persisted snapshots exclude raw conversation content. Real user messages should not be used in this prototype.

**What if APP Shield is wrong?** It exposes confidence, reasons, and proportionate interventions; users can cancel/verify/continue in simulation and uncertain cases can go to review. Real deployment would require human governance and outcome studies.

**Why not just use an LLM?** The prototype uses structured financial and graph features, deterministic policy, and optional text models. This supports bounded latency, repeatability, privacy control, and component-level failure handling; it still needs broader testing.

**How would a platform integrate it?** Conceptually, a payment request would call a risk service before orchestration, and the service would return risk, confidence, reason codes, and a context-check/intervention recommendation. This is not a claim of compatibility with any provider API.
