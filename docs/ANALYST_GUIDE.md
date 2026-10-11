# Analyst guide

Open **Analyst mode** from the control center or visit `/analyst`. This is a local synthetic-data investigation view, not a production fraud operations console.

## Investigate a payment

Select an attempt in the table or search by its payment-attempt ID. Filter by risk, scenario, decision, and recorded user action. Review the decision alongside:

- transaction-only and full APP Shield evidence scores;
- model confidence, clearly separated from risk;
- concerning reasons, protective evidence, and unavailable inputs;
- scenario and manipulation evidence;
- the observed, capped recipient-network neighborhood; and
- audit events for the decision and any later simulated action.

Network edges represent historical synthetic transfers. A graph connection is evidence for review, not proof of intent. The dashboard reports network-rule explanations from the returned backend evidence.

Use **Download case JSON** after selecting a case to export its actual payment fields, assessment, reasons, protective/unavailable evidence, model versions, and network response. The report includes a generation time and synthetic-data limitations. It does not create or imply a fraud label.

## Review and conclusions

The local review APIs can record a typed analyst outcome with an audit trail. Only authorized, provenance-bearing delayed labels enter the feedback pipeline. A user cancel/continue action is behavior data and must never be treated as a confirmed fraud label.

## Limits

Accounts, transactions, scenarios and labels in this project are synthetic. Do not use this demo to make decisions about real people or real payments. See the [API guide](API.md) for routes and data semantics.
