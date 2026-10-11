# User guide

APP Shield is a synthetic demonstration of pre-payment scam analysis. Use fictional data only; it is not connected to a payment provider.

## Analyze a payment

From the control center, choose **Analyze payment**. Choose a sender and recipient from the synthetic catalog, enter the amount, and optionally select the purpose. Review the details and run the safety check. If the engine needs context, answer only the questions it displays and optionally provide the conversation text. Do not enter PINs, OTPs, passwords, CVVs, or card details.

Results explain the action in plain language. A warning is not proof of fraud. A ready result means the current synthetic evidence did not trigger a stronger intervention; it is not a guarantee of safety. Confidence describes evidence certainty and is separate from the risk score.

A payment remains simulated. Canceling records a user action; it does not create a confirmed-scam label. Confirming a ready demo records a simulated completion only.

## Test a prepared scenario

Choose **Test a prepared scenario** to load a synthetic example such as a government impersonation attempt or a legitimate family emergency. The simulator applies the same backend pipeline as manual analysis. Its result is a model output, not a ground-truth label. Open analyst mode to inspect the case evidence.

## Recent analyses

The control center and **Transactions** page show local demo activity. A missing item can mean that no attempt has been created in this running session or that the backend is unavailable. Check **Demo readiness** on the control center before retrying.

## Understand the evidence

- **Risk** is the backend's evidence index and decision-policy input; it is not automatically a calibrated probability of fraud.
- **Confidence** summarizes evidence certainty; it is not the chance that the payment is fraudulent.
- **Protective evidence** is shown separately from concerning reasons.
- **Unavailable evidence** means the system could not use that source; it does not mean the source was safe.

See the [analyst guide](ANALYST_GUIDE.md) for technical case details.
