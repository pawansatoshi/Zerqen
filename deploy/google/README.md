# Zerqen Google Cloud worker

This deployment keeps the paper worker independent of the phone/browser.

## VM target

Use a Google Compute Engine Always Free eligible e2-micro in an eligible US region. Keep the worker lightweight and monitor egress.

## Install

1. Create the VM and install Python 3.12+ and git.
2. Clone this repository into /opt/zerqen.
3. Install the package: python3 -m pip install -e .
4. Create /etc/zerqen/worker.env from worker.env.example.
5. Set ZERQEN_API_BASE_URL, ZERQEN_DASHBOARD_TOKEN, and OPENROUTER_API_KEY.
6. Install the systemd unit: sudo cp deploy/google/zerqen-demo-worker.service /etc/systemd/system/
7. Run sudo systemctl daemon-reload && sudo systemctl enable --now zerqen-demo-worker

## Safety behavior

The worker only creates paper orders through /api/paper. Real trading remains disabled.

The AI agent is hard-gated to OpenRouter models whose live metadata reports both prompt and completion pricing as exactly zero. A paid model, pricing-unknown model, or non-zero reported inference cost is rejected. New zero-priced models are discovered automatically when the registry refreshes.

If no verified-free model is available, an AI-gated setup becomes HOLD/REJECTED rather than using a paid fallback.

The worker restarts automatically after a VM/process failure and survives browser/mobile shutdown.

## Verify

sudo systemctl status zerqen-demo-worker
journalctl -u zerqen-demo-worker -f

The dashboard /api/ai/status endpoint reports the verified free-model pool. /api/ai/models exposes the current registry to authenticated dashboard users.
