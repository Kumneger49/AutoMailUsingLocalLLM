# AutoMail Setup Guide

## Part 1: Gmail API Setup

To use the Gmail API integration, you need to set up OAuth2 credentials: 

### Steps:

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Create a new project or select an existing one

2. **Enable Gmail API**
   - Go to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

3. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Download the credentials JSON file
   - Rename it to `credentials.json` and place it in the project root directory

4. **Set up Pub/Sub (for webhook notifications)**
   - In Google Cloud Console, go to "APIs & Services" > "Library"
   - Enable "Cloud Pub/Sub API"
   - Create a topic and subscription for Gmail push notifications
   - **Grant Gmail permission to publish to your topic:**
     - Go to Pub/Sub > Topics > [Your Topic Name]
     - Click "PERMISSIONS" tab
     - Click "GRANT ACCESS"
     - Add principal: `gmail-api-push@system.gserviceaccount.com`
     - Select role: "Pub/Sub Publisher"
     - Click "SAVE"
   - **Configure Gmail to send notifications:**
     - Run the setup script: `python setup_gmail_watch.py`
     - Enter your full topic name (format: `projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME`)
     - The script will set up Gmail watch (expires after 7 days, needs renewal)

5. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

6. **First Run**
   - When you run the application for the first time, it will open a browser window
   - Sign in with your Google account
   - Grant permissions for Gmail access
   - A `token.json` file will be created automatically (this stores your credentials)

## Part 2: Running the Application

```bash
# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn EmailRead.notify:app --reload --port 8000
```

The webhook endpoint will be available at: `http://localhost:8000/pubsub/gmail`

## Part 3: Configuring Gmail Watch (One-time Setup)

After creating your Pub/Sub topic and subscription, you need to:

1. **Grant Gmail permission to publish to your topic:**
   - Go to [Google Cloud Console > Pub/Sub > Topics](https://console.cloud.google.com/cloudpubsub/topic/list)
   - Click on your topic name
   - Click the "PERMISSIONS" tab
   - Click "GRANT ACCESS"
   - In "New principals", add: `gmail-api-push@system.gserviceaccount.com`
   - In "Select a role", choose: `Pub/Sub Publisher`
   - Click "SAVE"

2. **Run the setup script:**
   ```bash
   python setup_gmail_watch.py
   ```
   - Enter your full topic name when prompted
   - Format: `projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME`
   - Example: `projects/my-project-123/topics/gmail-notifications`

3. **Important Notes:**
   - Gmail watch expires after **7 days** and needs to be renewed
   - Run `setup_gmail_watch.py` again before it expires
   - The watch monitors your INBOX for new emails

