"""
Script to configure Pub/Sub subscription to push messages to your webhook endpoint.
This sets up your subscription to automatically forward Gmail notifications to your FastAPI server.
"""

import os
from google.cloud import pubsub_v1
from google.oauth2 import service_account

def setup_push_subscription(
    project_id: str,
    subscription_name: str,
    push_endpoint: str
):
    """
    Configure a Pub/Sub subscription to push messages to a webhook endpoint.
    
    Args:
        project_id: Your GCP project ID (e.g., 'automail-476705')
        subscription_name: Name of your subscription (e.g., 'automailSub')
        push_endpoint: Full URL of your webhook endpoint (e.g., 'https://your-domain.com/pubsub/gmail')
    """
    try:
        # Initialize the subscriber client
        # Note: This requires service account credentials or gcloud auth
        subscriber = pubsub_v1.SubscriberClient()
        
        subscription_path = subscriber.subscription_path(project_id, subscription_name)
        
        # Configure push configuration
        push_config = pubsub_v1.types.PushConfig(
            push_endpoint=push_endpoint
        )
        
        # Update the subscription
        print(f"📡 Configuring subscription: {subscription_name}")
        print(f"   Push endpoint: {push_endpoint}")
        
        subscriber.modify_push_config(
            request={
                "subscription": subscription_path,
                "push_config": push_config
            }
        )
        
        print(f"\n✅ Subscription configured successfully!")
        print(f"   Messages will be pushed to: {push_endpoint}")
        
    except Exception as e:
        print(f"❌ Error configuring subscription: {e}")
        print("\n💡 Alternative: Configure via Google Cloud Console:")
        print(f"   1. Go to Pub/Sub > Subscriptions")
        print(f"   2. Click on: {subscription_name}")
        print(f"   3. Click 'EDIT'")
        print(f"   4. Under 'Delivery type', select 'Push'")
        print(f"   5. Enter endpoint URL: {push_endpoint}")
        print(f"   6. Click 'UPDATE'")


if __name__ == "__main__":
    print("="*60)
    print("Pub/Sub Push Subscription Setup")
    print("="*60)
    
    project_id = "automail-476705"
    subscription_name = "automailSub"
    
    print(f"\nProject ID: {project_id}")
    print(f"Subscription: {subscription_name}")
    
    print("\nEnter your webhook endpoint URL.")
    print("⚠️  IMPORTANT: The URL must include the full path: /pubsub/gmail")
    print("\nFor local development with ngrok:")
    print("  1. Start your server: uvicorn EmailRead.notify:app --port 8000")
    print("  2. In another terminal, run: ngrok http 8000")
    print("  3. Use the ngrok HTTPS URL + /pubsub/gmail")
    print("  Example: https://abc123.ngrok.io/pubsub/gmail")
    print("\nFor production:")
    print("  Example: https://your-domain.com/pubsub/gmail")
    
    push_endpoint = input("\nPush endpoint URL: ").strip()
    
    if not push_endpoint:
        print("❌ Endpoint URL cannot be empty!")
        exit(1)
    
    if not push_endpoint.startswith(('http://', 'https://')):
        print("⚠️  Warning: URL should start with http:// or https://")
    
    setup_push_subscription(project_id, subscription_name, push_endpoint)

