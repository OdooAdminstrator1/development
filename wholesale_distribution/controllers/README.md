# Wholesale Distribution — Mobile API (v1)

REST-ish **JSON-RPC** API the field mobile app uses to run distribution operations.

- **Base path:** `/api/v1/distribution`
- **Method:** every endpoint is HTTP `POST`
- **Content-Type:** `application/json`

---

## 1. Authentication — two tokens, **both required** on every request

The fleet shares **one** internal Odoo seat. Each physical distributer has their own **portal** user. So every request carries two Odoo API keys (both with scope `rpc`):

| Header | Value | Identifies |
| --- | --- | --- |
| `Authorization` | `Bearer <INTEGRATION_KEY>` | the internal integration user → **executes** all ORM work |
| `X-Distributer-Token` | `Bearer <DISTRIBUTER_KEY>` | the distributer's portal user → **who** is acting (identity) |

- The `Bearer ` prefix is recommended; a bare key string is also accepted on either header.
- From the distributer's portal user the server derives the **outlet** (the outlet whose *Default Distributor* is that user) and the **hr.employee**. The app **never** sends an outlet id or employee id.
- The distributer's portal user is stored as the run's `user_id` (its salesman).

**Generating keys** (one-time, in the Odoo backend):
`Settings → Users → (the user) → Account Security → New API Key`, scope = **rpc**.
Portal-user keys are typically generated server-side by an administrator.

---

## 2. Request / response envelope (JSON-RPC 2.0)

These routes are `type='jsonrpc'`. Send the endpoint payload inside `params` and read the payload back from `result`.

**Request body**
```json
{ "jsonrpc": "2.0", "method": "call", "id": 1, "params": { /* endpoint params */ } }
```

**Success** (HTTP 200)
```json
{ "jsonrpc": "2.0", "id": 1,
  "result": { "status": "success", "data": { /* endpoint data */ } } }
```

**Handled error** (HTTP 200 — business/auth errors are *returned*, not thrown)
```json
{ "jsonrpc": "2.0", "id": 1,
  "result": { "status": "error", "code": "<code>", "message": "<human text>" } }
```

**Error `code` values**

| code | meaning |
| --- | --- |
| `forbidden` | bad/missing token, or the record is not yours |
| `invalid_request` | missing/invalid param, or a business rule was violated |
| `server_error` | unexpected exception (also logged server-side) |

> **Transport errors** (malformed JSON, or a crash *outside* the handler) come back as a JSON-RPC **`error`** object instead of `result`. Always check for `result` first, then `result.status`.

No session cookie / CSRF token is needed (`auth='none'`, `csrf=False`); the two API keys are the only credentials.

**curl example**
```bash
curl -X POST https://HOST/api/v1/distribution/run/open \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer INTEGRATION_KEY" \
  -H "X-Distributer-Token: Bearer DISTRIBUTER_KEY" \
  -d '{"jsonrpc":"2.0","method":"call","id":1,"params":{}}'
```

---

## 3. Shared data shapes

**run_summary**
```js
{ run_id:int, name:str, state:str, outlet_id:int, outlet_name:str,
  start_date:"YYYY-MM-DD"|null, end_date:"YYYY-MM-DD"|null, currency_id:int,
  total_sale_orders:float, total_paid:float, total_validated:float, total_rest:float }
```

**order_summary**
```js
{ order_id:int, name:str, partner_id:int, partner_name:str,
  date_order:"YYYY-MM-DD HH:MM:SS"|null, state:str, amount_total:float,
  currency_id:int /*, payments:[payment_summary] (only in run/detail) */ }
```

**payment_summary**
```js
{ payment_id:int, date:"YYYY-MM-DD"|null, amount:float, currency_id:int,
  state:str, sale_order_id:int|null }
```

**Enumerations**

| field | values |
| --- | --- |
| `run.state` | `open`, `partial_closed`, `requires_validate`, `closed` |
| `payment.state` | `collected` (held by distributer), `validated` (posted by cashier) |
| `order.state` | standard sale.order: `draft`, `sent`, `sale`, `cancel` |

---

## 4. Endpoints

### `POST /api/v1/distribution/run/open`
Open (or receive the already-open) delivery run for the distributer.

- **Params:** _none_
- **Returns:** `{ run_id, name, state, outlet_id, outlet_name, distributer_employee_id }`
- **Notes:** Reuses the distributer's existing open run if any; otherwise creates one — but only if the **Distributors Can Open Runs** setting is enabled, else returns an error asking the cashier to open it.
- **Errors:** `forbidden` (auth); `invalid_request` (distributer has no outlet / not allowed to open).

### `POST /api/v1/distribution/order/create`
Create + confirm a distribution sale order (**no** picking, **no** invoice) on the distributer's current **open** run, with optional cash collected.

- **Params:**
  ```js
  {
    partner_id : int,    // required — customer
    lines : [ { product_id:int /*req*/, qty:float /*=1.0*/, price:float /*opt unit price*/ } ], // required, >= 1
    payments : [ { amount:float /*req*/, currency_id:int /*opt, default order currency*/ } ]      // optional
  }
  ```
- **Returns:** `{ order_id, name, state, amount_total, payment_ids:[int] }`
- **Errors:** `invalid_request` (no open run / missing `partner_id` / empty `lines` / unknown customer).

### `POST /api/v1/distribution/payment/add`
Record an extra cash collection (e.g. a late payment), even on an already (partially) closed run — which flips that run to `requires_validate` to alert the cashier.

- **Params:**
  ```js
  {
    amount : float,         // required
    sale_order_id : int,    // optional — run is taken from the order's delivery_run_id
    currency_id : int       // optional, default run currency
  }
  ```
- **Returns:** `{ payment_id, run_id, run_state, amount }`
- **Notes:** With no `sale_order_id`, the payment attaches to the distributer's most recent run (any state).
- **Errors:** `forbidden` (order/run not yours); `invalid_request` (no run / order has no run).

### `POST /api/v1/distribution/run/list`
List the distributer's runs (filter + pagination).

- **Params:** `{ states:[str] /*opt*/, limit:int /*=80*/, offset:int /*=0*/ }`
- **Returns:** `{ total:int, count:int, runs:[run_summary] }`

### `POST /api/v1/distribution/run/detail`
One run with its orders (each incl. payments) and run-level payments.

- **Params:** `{ run_id:int }` _(required)_
- **Returns:** `run_summary` **plus** `{ orders:[order_summary (with payments)], unlinked_payments:[payment_summary] }`
- **Errors:** `forbidden` (not yours); `invalid_request` (missing/unknown `run_id`).

### `POST /api/v1/distribution/catalog`
Sellable products with price (optionally for a given pricelist).

- **Params:** `{ search:str /*opt, matches name/internal-ref*/, pricelist_id:int /*opt*/, limit:int /*=80*/, offset:int /*=0*/ }`
- **Returns:** `{ total, count, products:[ { product_id, name, default_code, uom, list_price, price, currency_id, is_storable } ] }`
- **Notes:** `price` = pricelist unit price for qty 1 if `pricelist_id` given, else the product's `list_price`.

### `POST /api/v1/distribution/outlet/quantities`
On-hand stock currently inside the run's outlet location.

- **Params:** `{ run_id:int /*opt — defaults to the distributer's OPEN run*/ }`
- **Returns:** `{ run_id, location_id, location_name, lines:[ { product_id, name, uom, quantity, available_quantity } ] }`
- **Notes:** `available_quantity = on_hand − reserved`.
- **Errors:** `forbidden` (run not yours); `invalid_request` (no open run / no location).

### `POST /api/v1/distribution/order/search`
Search the distributer's distribution orders by customer / date.

- **Params:**
  ```js
  {
    partner_id : int,                       // optional
    date_from : "YYYY-MM-DD" | datetime,    // optional, inclusive
    date_to   : "YYYY-MM-DD" | datetime,    // optional, inclusive whole day
    limit : int /*=80*/, offset : int /*=0*/
  }
  ```
- **Returns:** `{ total, count, orders:[order_summary] }`
