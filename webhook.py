from flask import Flask, request, jsonify, send_from_directory
import database as db
import os
import json
import requests

# Initialize database tables
db.init_db()

app = Flask(__name__)

# Verification token for Meta webhook configuration
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "tpa_secure_verify_token_2026")

def get_meta_credentials():
    """Reads credentials from database settings to dynamically query Meta endpoints."""
    try:
        return {
            "ACCESS_TOKEN": db.get_setting("ACCESS_TOKEN"),
            "PHONE_NUMBER_ID": db.get_setting("PHONE_NUMBER_ID"),
            "WABA_ID": db.get_setting("WABA_ID")
        }
    except Exception as e:
        print(f"[ERROR] Failed to load credentials from DB settings: {e}")
        return {}

def download_whatsapp_media(media_id, filename):
    """Downloads binary media files from Meta Cloud API."""
    creds = get_meta_credentials()
    token = creds.get("ACCESS_TOKEN")
    
    if not token or token.startswith("YOUR_"):
        print("[ERROR] Cannot download media: Access Token not configured or invalid.")
        return False
        
    try:
        # Step 1: Get media URL from Meta metadata
        metadata_url = f"https://graph.facebook.com/v20.0/{media_id}"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        res = requests.get(metadata_url, headers=headers)
        if res.status_code != 200:
            print(f"[ERROR] Failed to fetch media metadata from Meta: {res.text}")
            return False
            
        media_url = res.json().get("url")
        if not media_url:
            print("[ERROR] Media URL not found in metadata response.")
            return False
            
        # Step 2: Download binary data using media URL
        media_res = requests.get(media_url, headers=headers)
        if media_res.status_code == 200:
            with open(filename, "wb") as f:
                f.write(media_res.content)
            print(f"[SUCCESS] Downloaded incoming media file to local workspace: {filename}")
            return True
        else:
            print(f"[ERROR] Failed to download media bytes: {media_res.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Media download crashed: {str(e)}")
        return False

def get_whatsapp_media_base64(media_id):
    """Downloads media from Meta Cloud API and returns its Base64 encoded string."""
    creds = get_meta_credentials()
    token = creds.get("ACCESS_TOKEN")
    
    if not token or token.startswith("YOUR_"):
        print("[ERROR] Cannot download media: Access Token not configured or invalid.")
        return None
        
    try:
        # Step 1: Get media URL from Meta metadata
        metadata_url = f"https://graph.facebook.com/v20.0/{media_id}"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        res = requests.get(metadata_url, headers=headers)
        if res.status_code != 200:
            print(f"[ERROR] Failed to fetch media metadata: {res.text}")
            return None
            
        media_url = res.json().get("url")
        if not media_url:
            return None
            
        # Step 2: Download binary data using media URL
        media_res = requests.get(media_url, headers=headers)
        if media_res.status_code == 200:
            import base64
            b64_str = base64.b64encode(media_res.content).decode("utf-8")
            return b64_str
        else:
            print(f"[ERROR] Failed to download media bytes: {media_res.text}")
            return None
            
    except Exception as e:
        print(f"[ERROR] Base64 download crashed: {str(e)}")
        return None

@app.route("/", methods=["GET"])
def home():
    return "TPA Webhook Server with Image Downloader is RUNNING!", 200

@app.route("/media/<filename>", methods=["GET"])
def serve_media(filename):
    """Serves WhatsApp media files with on-demand self-healing download capability from Meta."""
    if not os.path.exists(filename):
        # Self-healing proxy: if the file was deleted or instance restarted, download it dynamically
        if filename.startswith("incoming_") and filename.endswith(".png"):
            media_id = filename.replace("incoming_", "").replace(".png", "")
            print(f"[MEDIA PROXY] File {filename} not found. Fetching on-demand for media_id: {media_id}")
            download_success = download_whatsapp_media(media_id, filename)
            if not download_success:
                return "Media not found on Meta API", 404
        else:
            return "File not found", 404
            
    return send_from_directory(".", filename)

@app.route("/debug-db", methods=["GET"])
def debug_db():
    creds = get_meta_credentials()
    db_type = "PostgreSQL (Supabase)" if db.DATABASE_URL and db.PSYCOPG2_AVAILABLE else "SQLite (Local fallback)"
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages")
        msg_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM clients")
        client_count = cursor.fetchone()[0]
        conn.close()
        return jsonify({
            "status": "connected",
            "db_type": db_type,
            "has_database_url": bool(db.DATABASE_URL),
            "psycopg2_available": db.PSYCOPG2_AVAILABLE,
            "message_count": msg_count,
            "client_count": client_count,
            "config_credentials": {
                "has_token": bool(creds.get("ACCESS_TOKEN")),
                "phone_id": creds.get("PHONE_NUMBER_ID"),
                "waba_id": creds.get("WABA_ID")
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "db_type": db_type,
            "error": str(e)
        }), 500


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Handles GET request verification for Meta WhatsApp Cloud API webhooks."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("[INFO] Webhook Verified Successfully by Meta!")
            return challenge, 200
        else:
            print("[ERROR] Webhook verification failed. Token mismatch.")
            return "Verification token mismatch", 403
            
    return "Invalid Request", 400

@app.route("/webhook", methods=["POST"])
def capture_message():
    """Handles incoming message notifications dispatched from Meta."""
    data = request.json
    print(f"[DEBUG] Incoming Webhook Data: {data}")
    
    if not data:
        return jsonify({"status": "ignored", "reason": "No body"}), 200
        
    # Check if this is a WhatsApp Business Account message event
    if data.get("object") == "whatsapp_business_account":
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                
                # Check if there are messages in the value payload
                if "messages" in value:
                    for msg in value.get("messages", []):
                        from_phone = msg.get("from")
                        msg_id = msg.get("id")
                        msg_type = msg.get("type")
                        
                        # Extract profile name of the contact
                        contact_name = "WhatsApp Contact"
                        for contact in value.get("contacts", []):
                            if contact.get("wa_id") == from_phone:
                                contact_name = contact.get("profile", {}).get("name", "WhatsApp Contact")
                                break
                        
                        # Process text messages
                        if msg_type == "text":
                            body = msg.get("text", {}).get("body", "")
                            print(f"[INBOX] Incoming TEXT from {contact_name} ({from_phone}): '{body}'")
                            
                            # Save text message to DB
                            db.save_message(from_phone, "client", body, msg_id)
                            
                        # Process image messages
                        elif msg_type == "image":
                            image_id = msg.get("image", {}).get("id")
                            filename = f"incoming_{image_id}.png"
                            
                            print(f"[INBOX] Incoming IMAGE from {contact_name} ({from_phone}). Attempting download...")
                            
                            # Download the image file locally (for local execution compatibility)
                            download_success = download_whatsapp_media(image_id, filename)
                            
                            # Fetch base64 representation for shared cloud db sync
                            media_b64 = get_whatsapp_media_base64(image_id)
                            
                            # Construct public Render URL for the image
                            public_media_url = f"https://tpa-poster-sender.onrender.com/media/{filename}"
                            
                            # Save media message details with public Render media URL and base64 representation to DB
                            db.save_message(from_phone, "client", f"📷 Incoming Image: {public_media_url}", msg_id, media_b64=media_b64)
                            
                        else:
                            # Handle other types like documents, buttons, etc.
                            body = f"[Sent a {msg_type} message]"
                            db.save_message(from_phone, "client", body, msg_id)
                            print(f"[INBOX] Received non-text message type: {msg_type} from {from_phone}")
                        
                        # Auto-register client in clients database if not present
                        try:
                            _, count = db.get_clients_dataframe(search_query=from_phone)
                            if count == 0:
                                client_id = f"LEAD-{from_phone[-4:]}"
                                db.add_client(
                                    client_id=client_id, 
                                    name=contact_name, 
                                    phone=from_phone, 
                                    category="Incoming Lead", 
                                    status="Active"
                                )
                                print(f"[DB] Auto-registered new client: {contact_name} ({from_phone})")
                        except Exception as e:
                            print(f"[ERROR] Auto-registering client failed: {str(e)}")
                                
    return jsonify({"status": "processed"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"=============================================")
    print(f"[Webhook] Server starting on port {port}...")
    print(f"[Webhook] Verification Token: {VERIFY_TOKEN}")
    print(f"[Webhook] Local Endpoint: http://localhost:{port}/webhook")
    print(f"=============================================")
    app.run(host="0.0.0.0", port=port, debug=False)
