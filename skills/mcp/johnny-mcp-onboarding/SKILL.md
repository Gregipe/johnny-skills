---
name: johnny-mcp-onboarding
description: "Use when onboarding MCP servers (Zomato, Razorpay)."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [mcp, integrations, zomato, oauth, johnny]
    category: mcp
---

# MCP Service Onboarding (Greg's profiles)

## When to Use

- Adding a transactional MCP server (Zomato, Razorpay, Swiggy, Kite) to Greg's profiles
- Fixing OAuth login failures, disabled-server saves, or post-restart tool discovery for MCP servers
- Re-verifying an MCP integration end-to-end after config changes

Procedure for wiring transactional MCP servers into Hermes (johnny profile) — Zomato was the
first, Oct 2026. Native MCP client docs: native-mcp skill.

## Zomato

- Endpoint: `https://mcp-server.zomato.com/mcp` (remote HTTP, OAuth 2.0 browser flow)
- Config: `hermes mcp add zomato --url https://mcp-server.zomato.com/mcp --auth oauth`
- Auth: Zomato account = Greg's phone number + OTP. On a server host there is no local browser —
the flow prints an authorize URL for Greg to open manually; see "Headless OAuth re-login" below.
Tokens are cached locally after success.
- 10 tools: get_restaurants_for_keyword, get_restaurant_menu_by_categories,
get_menu_items_listing, get_saved_addresses_for_user, create_cart, checkout_cart,
get_order_history, get_order_tracking_info, bind_user_number(_verify_code).
- SAFETY RULE: Zomato orders are real money. Always confirm the full order (restaurant,
items, address, payment method) with Greg BEFORE checkout_cart. Never place an order he
hasn't explicitly approved. create_cart's own tool description demands asking the payment
method — comply.

## Pitfalls (cost us two OAuth rounds)

- Default oauth timeout is 30s — phone-OTP logins take 60-120s and the callback races it.
BEFORE running the flow, set: `hermes config set mcp_servers.<name>.oauth.timeout 900` and
`hermes config set mcp_servers.<name>.connect_timeout 180`. On a chat platform the paste-back
round trip (Greg opens the URL, logs in, copies the redirect, sends it back) routinely exceeds
300s — at 300 the waiting login dies with 'OAuth callback timed out' and everything must restart.
- If the add-time connect fails, the server saves DISABLED. Re-enable with
`hermes config set mcp_servers.<name>.enabled true`, then `hermes mcp login <name> --flow browser`.
- `hermes mcp add` is interactive (two prompts: 'continue without auth' + 'save anyway').
Run it with pty=true + background=true and answer via process_manage submit; the first
prompt consumes input before the save prompt, so submit "n" then "y" in order.
- No hot-reload: MCP tools appear in long-lived processes only after restart
(`hermes gateway restart` for the messaging gateway; /new for TUI sessions).
Fresh one-shot processes (`hermes -z`, dashboard bridge chat runs) get them immediately.
- Verify E2E before declaring done: `hermes mcp test <name>` for the connection + tool list,
then a read-only `hermes -z` prompt calling one of the tools (e.g. list saved addresses).
- Tokens expire or vanish while config stays enabled — symptom: the server's tools are silently
absent (tool_search finds none) and `hermes mcp test <name>` reports 'no cached tokens found'.
Check state with `hermes mcp list` (there is no `hermes mcp status` command).

## Headless OAuth re-login (server host, Greg remote)

1. Start `hermes mcp login <name> --flow browser` with background=true + pty=true.
2. Poll output (process_manage poll) for the authorize URL; send it to Greg to open on his own device.
3. The redirect_uri is a localhost callback — on Greg's device the redirect lands on an error page;
the `?code=...&state=...` is in the browser address bar. Have him paste the FULL redirect URL back.
4. Submit it to the waiting login prompt (process_manage submit), then verify with `hermes mcp test <name>`.
5. If the submit returns 'already exited', the flow timed out — the pasted code is dead (state
and PKCE are bound to that flow instance). Restart the login and send Greg the FRESH URL;
his browser session persists, so re-approval is usually one tap and no new OTP.

## Indian MCP landscape (researched Oct 2026, all verified with source URLs)

Official: Razorpay, Cashfree, Pine Labs, Juspay, Paytm, PhonePe (docs), Setu, Zerodha Kite,
Groww, Upstox, Dhan, 5paisa, HDFC SKY, NSE (nseindia.com/nse-mcp, free data), Fi Money,
Perfios Kscan, PolicyBazaar, Zoho (CRM/Books/Creator/Cliq/Analytics/Payments), Freshworks,
Chargebee, MoEngage, CleverTap, Darwinbox, BrowserStack (mcp.browserstack.com), LambdaTest/TestMu,
Exotel (voice/SMS/VoiceBots — most relevant to Hunar domain), Postman, Hasura PromptQL,
Sarvam AI (STT/TTS/translation), Ola Krutrim Cloud (docs.cloud.olakrutrim.com/mcp/overview),
Yellow.ai (docs only), Swiggy, Zomato, Shiprocket (shipping), GoKwik KwikCheckout.
Community only: Blinkit, Zepto, BigBasket, Flipkart, Myntra, Dukaan, Gupshup, Kissflow,
Kaleyra, Angel One, ICICI Direct, India Stack (github.com/rehan1020/mcp-india-stack).
None found: CRED, BharatPe, Jupiter, Niyo, Nium, Lendingkart, IRCTC, DigiLocker, ISRO.

## Pitfall: GLM-5.3 delegation balance

delegate_task children inherit delegation.provider/model from config.yaml (pinned glm-5.3).
When GLM credits run out children die mid-task with HTTP 429 (Zai balance exhausted) while the
main session (deepseek) keeps working. Re-pin with hermes config set delegation.provider deepseek
+ delegation.model deepseek-v4-pro, or top up GLM.
