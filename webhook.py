from flask import Flask, request, jsonify
import database as db
import os

# Initialize database tables
db.init_db()

app = Flask(__name__)

# Verification token for Meta webhook configuration
# You will paste this token in Meta App Developer Console (Webhooks section)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "tpa_secure_verify_token_2026")

@app.route("/", methods=["GET"])
def home():
    return "TPA Webhook Server is RUNNING!", 200

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
                        
                        # Process text messages
                        if msg_type == "text":
                            body = msg.get("text", {}).get("body", "")
                            
                            # Extract profile name of the contact
                            contact_name = "WhatsApp Contact"
                            for contact in value.get("contacts", []):
                                if contact.get("wa_id") == from_phone:
                                    contact_name = contact.get("profile", {}).get("name", "WhatsApp Contact")
                                    break
                                    
                            print(f"[INBOX] Incoming message from {contact_name} ({from_phone}): '{body}'")
                            
                            # 1. Save the incoming message
                            db.save_message(from_phone, "client", body, msg_id)
                            
                            # 2. Check if client exists in clients database, if not, auto-create a lead!
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
                                
                        else:
                            # Handle other types like images, documents, buttons, etc.
                            body = f"[Sent a {msg_type} message]"
                            db.save_message(from_phone, "client", body, msg_id)
                            print(f"[INBOX] Received non-text message type: {msg_type} from {from_phone}")
                            
    return jsonify({"status": "processed"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"=============================================")
    print(f"📡 Webhook server starting on port {port}...")
    print(f"🔑 Verification Token: {VERIFY_TOKEN}")
    print(f"🔗 Local Webhook Endpoint: http://localhost:{port}/webhook")
    print(f"=============================================")
    app.run(host="0.0.0.0", port=port, debug=False)
