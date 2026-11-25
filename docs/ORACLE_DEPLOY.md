# Deploying on Oracle Cloud Always Free (recommended target)

Free forever: 2 vCPU / 12GB ARM VM — runs the full stack (LaBSE + FastAPI + SQLite, plus a small local qwen3 model
as an optional fallback). The demo's answers come from Amazon Bedrock when a Bedrock key is set.
Costs $0 after signup; the credit card is only used for identity verification.

## Step 1 — Sign up (10 min)

1. Go to https://www.oracle.com/cloud/free/ → "Start for free"
2. Fill details + credit card (not charged). Use your real name matching the card.
3. Choose **home region carefully** (fixed forever, free resources live here):
   - For low latency in India try **Mumbai** or **Hyderabad** — but free ARM capacity
     there is often exhausted ("Out of capacity" error). If that happens, retry a few
     times over a day, or pick **Frankfurt / London / Amsterdam / Singapore**.
4. After signup, log in to https://cloud.oracle.com

## Step 2 — Create the VM (10 min)

1. Menu → Compute → Instances → **Create instance**
2. Name: `healthbot`, image: **Ubuntu 24.04**, shape: **Ampere / VM.Standard.A1.Flex**
   → set **2 OCPU / 12 GB** (the Always Free allowance; 1 OCPU/6GB also works but 2/12 is faster)
3. Add your **SSH public key** (generate one if you don't have one:
   `ssh-keygen -t ed25519` on your PC, paste the `.pub` content). This is how you'll log in.
4. Create. Once the instance is **Running**, note its **Public IP**.

## Step 3 — Open the firewall (2 min, easily forgotten!)

In the Oracle console:
1. Instance details → **Attached VNIC** → click the subnet → **Default Security List**
2. **Add Ingress Rules**: `TCP` / port `8000` / source `0.0.0.0/0` (and later 80/443 for WhatsApp)

## Step 4 — Get the code onto the VM

Use your own copy of this repo (fork it, or keep it private), then on the VM:

```bash
ssh ubuntu@<PUBLIC_IP>
sudo bash -c "curl -fsSL https://raw.githubusercontent.com/salman-mohammad-khan/aarogyasathi-rag/main/scripts/oracle_setup.sh -o /tmp/setup.sh"
sudo REPO_URL=https://github.com/salman-mohammad-khan/aarogyasathi-rag.git bash /tmp/setup.sh
```

Alternatively, upload the project folder with FileZilla/WinSCP to `/opt/healthbot` and
run `sudo bash scripts/oracle_setup.sh` (the script skips cloning if the folder exists).

## Step 5 — Configure and verify

```bash
sudo nano /opt/healthbot/.env        # set AWS_BEARER_TOKEN_BEDROCK (the answer model)
sudo systemctl restart healthbot
curl http://localhost:8000/api/health   # {"llm": {"backend": "bedrock", ...}} (or "cloud" / "local" without a Bedrock key)
```

Open `http://<PUBLIC_IP>:8000` in your browser — the bot is live on the cloud. For a public link, add a domain and
HTTPS in the next step, then close port 8000.

## Step 6 — HTTPS on your own subdomain (recommended)

Example: `aarogyasathi.example.com` (the live demo uses a subdomain of the author's own domain).

1. **DNS:** add an `A` record named `aarogyasathi` that points to the VM's public IP.
2. **Oracle security list:** add ingress rules for TCP ports `80` and `443` from `0.0.0.0/0` (like port 8000 in
   Step 3). Port 80 is needed for the certificate check.
3. **VM firewall** (Oracle's Ubuntu image blocks them by default):

```bash
sudo iptables -I INPUT 5 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save        # keep the rules after a reboot
```

4. **Caddy** gets and renews a free Let's Encrypt certificate and forwards to the app. Install it from Caddy's
   apt repository (see https://caddyserver.com/docs/install), then put this in `/etc/caddy/Caddyfile`:

```
aarogyasathi.example.com {
	encode gzip
	reverse_proxy 127.0.0.1:8000 {
		transport http {
			response_header_timeout 180s
		}
	}
}
```

```bash
sudo systemctl enable --now caddy
curl -I https://aarogyasathi.example.com/api/health
```

5. **WhatsApp (optional):** set `WHATSAPP_ENABLED=true`, the `WHATSAPP_*` values and `ADMIN_TOKEN` (for the test
   route) in `/opt/healthbot/.env` (see `.env.example`) and restart the service.
6. **Close port 8000** in the security list and the VM firewall once everything uses the HTTPS address. Caddy still
   reaches the app on `127.0.0.1:8000`.

## Managing the machine

```bash
journalctl -u healthbot -f            # logs
sudo systemctl restart healthbot      # restart app
```

Stopping when not needed (optional — free tier costs nothing when running):

```bash
# from your PC, after installing OCI CLI and configuring it once:
oci compute instance action --instance-id <OCID> --action STOP
oci compute instance action --instance-id <OCID> --action START
```

## Why this setup

- With `AWS_BEARER_TOKEN_BEDROCK` set, Amazon Bedrock (Gemma 3 27B, `ap-south-1`) answers first; if a call fails the bot
  answers from fixed templates
- Without a Bedrock key the bot answers from its fixed templates (see "Answer model" in the README)
- systemd keeps the bot running 24/7 (WhatsApp-ready, no cold starts)
- WhatsApp needs an HTTPS webhook URL: Step 6 provides it (Caddy + Let's Encrypt on port 443), and the webhook points
  to the same app
