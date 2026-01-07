# Fix Push Subscription Endpoint

## The Problem
Your Pub/Sub subscription is configured to push to `/` but your endpoint is at `/pubsub/gmail`.

## Solution: Update Push Subscription URL

### Option 1: Via Google Cloud Console (Easiest)

1. Go to [Pub/Sub Subscriptions](https://console.cloud.google.com/cloudpubsub/subscription/list?project=automail-476705)
2. Click on your subscription: **automailSub**
3. Click **"EDIT"** button
4. Under **"Delivery type"**, make sure **"Push"** is selected
5. In **"Endpoint URL"**, enter your full URL with the correct path:
   - For local testing with ngrok: `https://your-ngrok-url.ngrok.io/pubsub/gmail`
   - For production: `https://your-domain.com/pubsub/gmail`
6. Click **"UPDATE"**

### Option 2: Using the Setup Script

If you have ngrok or a public URL set up, run:
```bash
python setup_push_subscription.py
```

Enter your full endpoint URL including the path: `https://your-url/pubsub/gmail`

## For Local Development: Use ngrok

Since Pub/Sub needs a public HTTPS URL, you need to expose your local server:

1. **Install ngrok** (if not already installed):
   ```bash
   brew install ngrok  # macOS
   # or download from https://ngrok.com/
   ```

2. **Start your FastAPI server** (in one terminal):
   ```bash
   cd EmailRead
   uvicorn notify:app --reload --port 8000
   ```

3. **Start ngrok** (in another terminal):
   ```bash
   ngrok http 8000
   ```

4. **Copy the HTTPS URL** from ngrok (e.g., `https://abc123.ngrok.io`)

5. **Update your push subscription** to: `https://abc123.ngrok.io/pubsub/gmail`

## Verify It's Working

After updating, you should see:
- ✅ `INFO: "POST /pubsub/gmail HTTP/1.1" 200 OK` instead of 404
- 📩 Gmail notification received messages in your logs

