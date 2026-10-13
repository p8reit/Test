# Jita Ledger

An EVE Online trading research prototype for a 50B ISK portfolio and a 500M–1B net daily target. Python 3.12+, no third-party packages.

## Run

```sh
cd /workspace/Test
python3 -m unittest discover -s tests -v
python3 app.py --port 8000
```

The server binds to loopback only. Use local requests for validation; cloud onboarding does not provide a browser preview. On your own machine, open the local port in your browser. This is a single-user development application, not a hardened public service.

## What works

- Dashboard with configurable capital, goal, location IDs, and fee assumptions.
- Clearly labeled synthetic demo; demo records are never live quotes.
- Read-only public ESI collection for The Forge regional orders and contracts, complete endpoint pagination, persisted HTTP expiry cache, bounded retries, TLS verification, and conservative data age.
- Single-item fungible item-exchange contract filtering; excludes mixed, wanted, blueprint-copy, expired, and incompatible-location listings. Discovery is limited to ESI categories 4, 5, 8, 17, 20, 42, and 43 because public contract items lack a reliable packaged flag; ships and modules are excluded.
- Candidate discovery from available orders and comparable contracts, beyond a fixed item whitelist. To bound request volume, each refresh inspects at most 150 eligible contract item records, newest listings first; this is not an exhaustive scan.
- Actual order-depth acquisition costing, two candidate types maximum, shared capital constraints, configurable per-bundle charges and hauling, hypothetical sell targets and profit if all units sell.
- Persisted completed-batch journal recording actual net profit and hours to final sale.
- Strict output: zero qualified trades until completed-sale evidence and an independently validated forecasting model exist. Research candidates are never high-certainty recommendations.

## Important limitations

Jita 4-4 (`60003760`) is only a reference location, not a tax-free structure. Supply actual location IDs and verify fees. Current live acquisition mode handles public regional sell orders (immediate purchases); authenticated structure orders, buy-order fill prediction, EVE SSO, wallet reconciliation, inventory tracking, and probability calibration are not implemented. A private structure ID may yield no acquisition records until authenticated collection is added.

Contract asks are not completed-sale prices. A disappearing contract is not counted as sold. Hypothetical quantities use acquisition depth and half the available capital per type, not proven daily contract demand. Sale targets undercut comparable unit asks by 0.1%; they are exploratory hypotheses. A single hypothetical contract bundle is used per item allocation; adjust charges accordingly. Exact bundle-size demand is not modeled. No loss limit or liquidation forecast is implemented.

Manual journal entries include only fully sold batches; they cannot establish a daily win rate without attempted and unsold positions. There is no claim that 1–2% daily is achievable. Model calibration, larger-volume collection, and route-specific sell-through validation are future work.

## Data and access

SQLite data and HTTP cache live in ignored `.data/ledger.sqlite`. The latest 30 live snapshots are retained for research; only acquisition orders for eligible discovered item types are retained in those snapshots. They are partial observations, not a complete historical contract tape. Settings and journal persist across restarts; processes do not. API writes require JSON and reject cross-origin requests. No secrets are stored by this version. Do not put tokens in source control or chat.

Live refresh needs HTTPS access to `esi.evetech.net`. An initial proxy policy denial resolved after the domain addition was saved. Live status, market orders, and public contract listing payloads were verified in this instance. Configuration changes and startup instructions are saved as a draft; publication remains a user action. Demo and local accounting run without external access. Endpoints use standard `/latest/` ESI routes.

## Next implementation steps

1. Confirm exact purchasing structure, contract location, purchase method, and actual fees.
2. Enable ESI networking and verify live payloads, pagination, cache behavior, and structure access requirements.
3. Add minimal-scope EVE SSO and personal contract/wallet reconciliation with secure token storage.
4. Track attempts, unsold inventory, bundle sizes, fees, and actual fill times; collect enough observations for chronological out-of-sample validation.
5. Calibrate route/item-specific forecasts and downside estimates. Only then enable zero-to-two qualified daily recommendations, sized to conservative sell-through and the full-capital profit objective.
