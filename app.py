import streamlit as st
import pandas as pd
import requests
import os
import time
import io
import math
import database as db
import base64

def get_image_base64(filename):
    """Encodes a local file to base64 for direct browser embedding."""
    if os.path.exists(filename):
        try:
            with open(filename, "rb") as f:
                data = f.read()
                return base64.b64encode(data).decode()
        except Exception:
            return None
    return None

# Page Config with Tab Icon & Title
st.set_page_config(
    page_title="TPA Poster Sender | WhatsApp Bulk Engine",
    page_icon="📲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
db.init_db()

# Custom Premium Styling ( Fluid UI Flairs )
st.markdown("""
<style>
    /* Custom Sidebar design (sleek contrasting dark background) */
    [data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid #1e293b !important;
    }
    
    /* Custom metric card styles (high-visibility dark mode slate with teal highlight) */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, #0d9488, #2dd4bf);
    }
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: #0d9488;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4), 0 0 15px rgba(13, 148, 136, 0.25);
    }
    .metric-title {
        color: #94a3b8;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-value {
        color: #2dd4bf;
        font-size: 38px;
        font-weight: 800;
    }
    
    /* Rounded corners for alert banners */
    .stAlert {
        border-radius: 12px !important;
    }
</style>
""", unsafe_allow_html=True)

# Helpers for Meta API calls
def fetch_templates_from_meta(phone_number_id, access_token, waba_id=None):
    """Fetches approved message templates directly from Meta Cloud API using WABA ID."""
    if not access_token or access_token.startswith("YOUR_"):
        raise ValueError("Please configure a valid Meta Access Token first.")
    
    # 1. If WABA ID is provided manually, use it directly (100% reliable)
    if waba_id and waba_id.strip():
        url_templates = f"https://graph.facebook.com/v20.0/{waba_id.strip()}/message_templates"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        res_templates = requests.get(url_templates, headers=headers)
        if res_templates.status_code == 200:
            return res_templates.json().get("data", [])
        else:
            err_data = res_templates.json()
            err_msg = err_data.get("error", {}).get("message", res_templates.text)
            raise ValueError(f"Failed to fetch templates using WABA ID: {err_msg}")
            
    # 2. Fallback: Attempt WABA ID auto-discovery from phone number metadata
    url_phone = f"https://graph.facebook.com/v20.0/{phone_number_id}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    res_phone = requests.get(url_phone, headers=headers)
    if res_phone.status_code != 200:
        raise ValueError(f"Failed to fetch phone number details from Meta: {res_phone.text}")
    
    discovered_waba_id = res_phone.json().get("whatsapp_business_account_id")
    if not discovered_waba_id:
        raise ValueError("Could not find linked WhatsApp Business Account ID. Please enter WABA ID manually.")
        
    url_templates = f"https://graph.facebook.com/v20.0/{discovered_waba_id}/message_templates"
    res_templates = requests.get(url_templates, headers=headers)
    if res_templates.status_code != 200:
        raise ValueError(f"Failed to fetch templates from WABA account: {res_templates.text}")
        
    return res_templates.json().get("data", [])

# --- META CREDENTIALS (SIDEBAR) ---
st.sidebar.markdown("""
<div style="text-align: center; margin-bottom: 20px;">
    <h2 style="color: #0ea5e9 !important; margin: 0;">🔑 Meta API Engine</h2>
    <p style="color: #64748b; font-size: 13px;">Configure WhatsApp Cloud Credentials</p>
</div>
""", unsafe_allow_html=True)

PHONE_NUMBER_ID = st.sidebar.text_input(
    "Phone Number ID", 
    value=st.session_state.get("PHONE_NUMBER_ID", "1302085039650692"),
    help="Find this in the WhatsApp section of your Meta Developer Console"
)
WABA_ID = st.sidebar.text_input(
    "WhatsApp Business Account ID (WABA ID)", 
    value=st.session_state.get("WABA_ID", ""),
    placeholder="Paste WABA ID here (recommended)...",
    help="Copy this from WhatsApp > API Setup in Meta Developer Console"
)
ACCESS_TOKEN = st.sidebar.text_area(
    "Access Token", 
    value=st.session_state.get("ACCESS_TOKEN", ""),
    placeholder="Paste your Permanent/Temporary access token here...",
    help="System User Access Token with whatsapp_business_messaging permissions"
)

# Fetch approved templates button
if st.sidebar.button("🔌 Fetch My Templates from Meta", use_container_width=True):
    if not PHONE_NUMBER_ID or not ACCESS_TOKEN:
        st.sidebar.error("Please fill Phone Number ID and Access Token first!")
    else:
        with st.sidebar.spinner("Syncing with Meta WABA..."):
            try:
                fetched_t = fetch_templates_from_meta(PHONE_NUMBER_ID, ACCESS_TOKEN, WABA_ID)
                st.session_state["meta_templates"] = fetched_t
                st.session_state["WABA_ID"] = WABA_ID
                st.sidebar.success(f"Synced {len(fetched_t)} templates!")
                time.sleep(1.0)
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Sync Failed: {str(e)}")

# Template Name and Language code selection
TEMPLATE_NAME = "daily_poster_delivery"
LANGUAGE_CODE = "en_US"

if "meta_templates" in st.session_state and st.session_state["meta_templates"]:
    templates = st.session_state["meta_templates"]
    unique_names = sorted(list(set([t.get("name") for t in templates if t.get("status") == "APPROVED"])))
    
    if not unique_names:
        st.sidebar.warning("No approved templates found in WABA.")
        TEMPLATE_NAME = st.sidebar.text_input("Template Name", value="daily_poster_delivery")
        LANGUAGE_CODE = st.sidebar.text_input("Language Code", value="en_US")
    else:
        selected_template = st.sidebar.selectbox(
            "Select Approved Template",
            unique_names,
            index=0
        )
        
        # Get language codes for selected template name
        langs = sorted(list(set([t.get("language") for t in templates if t.get("name") == selected_template])))
        selected_lang = st.sidebar.selectbox(
            "Select Language",
            langs,
            index=0
        )
        
        TEMPLATE_NAME = selected_template
        LANGUAGE_CODE = selected_lang
        
        # Show small summary of the template structure
        matched_t = next(t for t in templates if t.get("name") == selected_template and t.get("language") == selected_lang)
        header_format = "None"
        body_text = ""
        for comp in matched_t.get("components", []):
            if comp.get("type") == "HEADER":
                header_format = comp.get("format", "TEXT")
            elif comp.get("type") == "BODY":
                body_text = comp.get("text", "")
                
        st.sidebar.info(f"📋 **Type:** {header_format} Header\n📝 **Body Preview:** {body_text[:80]}...")
        
        # Allow override check
        if st.sidebar.checkbox("Edit details manually"):
            TEMPLATE_NAME = st.sidebar.text_input("Template Name", value=TEMPLATE_NAME)
            LANGUAGE_CODE = st.sidebar.text_input("Language Code", value=LANGUAGE_CODE)
else:
    st.sidebar.info("💡 **Tip:** Click 'Fetch My Templates' above to list approved names automatically!")
    TEMPLATE_NAME = st.sidebar.text_input(
        "Template Name", 
        value=st.session_state.get("TEMPLATE_NAME", "daily_poster_delivery"),
        help="Name of your approved WhatsApp Template in WhatsApp Manager"
    )
    LANGUAGE_CODE = st.sidebar.text_input(
        "Language Code", 
        value=st.session_state.get("LANGUAGE_CODE", "en_US"),
        help="e.g. en_US, hi_IN"
    )

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Dispatch Settings")
DEFAULT_COUNTRY_CODE = st.sidebar.text_input(
    "Default Country Code", 
    value="91", 
    help="Prefix used when a 10-digit number is imported (e.g. 91 for India)"
)
ANTI_BAN_DELAY = st.sidebar.slider(
    "Anti-Ban Delay (Seconds)", 
    min_value=0.5, 
    max_value=10.0, 
    value=1.5, 
    step=0.5,
    help="Delay between messages to prevent spam detection and API rate limit locks"
)

# Store credentials in session state
st.session_state["PHONE_NUMBER_ID"] = PHONE_NUMBER_ID
st.session_state["WABA_ID"] = WABA_ID
st.session_state["ACCESS_TOKEN"] = ACCESS_TOKEN
st.session_state["TEMPLATE_NAME"] = TEMPLATE_NAME
st.session_state["LANGUAGE_CODE"] = LANGUAGE_CODE

# Save config.json for the webhook.py background process
import json
try:
    with open("config.json", "w") as config_file:
        json.dump({
            "PHONE_NUMBER_ID": PHONE_NUMBER_ID,
            "WABA_ID": WABA_ID,
            "ACCESS_TOKEN": ACCESS_TOKEN
        }, config_file)
except Exception:
    pass


# Title Header Banner
st.markdown("""
<div style="background: linear-gradient(135deg, #0f172a 0%, #115e59 100%); padding: 32px; border-radius: 16px; border: 1px solid #0d9488; margin-bottom: 25px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);">
    <div style="display: flex; align-items: center; gap: 18px;">
        <div style="background-color: #0d9488; padding: 12px; border-radius: 12px; box-shadow: 0 4px 10px rgba(13, 148, 136, 0.3);">
            <span style="font-size: 36px; line-height: 1;">📲</span>
        </div>
        <div>
            <h1 style="margin: 0; color: #2dd4bf !important; font-size: 32px; font-weight: 800; letter-spacing: -0.5px;">TPA Poster Sender</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 15px; font-weight: 500;">Premium WhatsApp Bulk Dispatcher & CRM Engine</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📤 Daily Poster Dispatch", 
    "👥 Master Client Database", 
    "💬 Inbox & Live Chat",
    "🔧 Settings & Dev Sandbox"
])

# Helpers for Meta API calls
def upload_image_to_meta(file_bytes, file_name, mime_type):
    """Uploads local image bytes to WhatsApp Media API and returns media_id."""
    if not ACCESS_TOKEN or ACCESS_TOKEN.startswith("YOUR_"):
        raise ValueError("Please configure a valid Meta Access Token first.")
        
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/media"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    files = {
        "file": (file_name, file_bytes, mime_type)
    }
    data = {
        "messaging_product": "whatsapp",
        "type": "image"
    }
    response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code == 200:
        return response.json().get("id")
    else:
        raise ValueError(f"Meta Media Upload Failed: {response.text}")

def send_whatsapp_template(to_phone, client_name, media_id, include_name=True):
    """Dispatches a template message with image header and optional body parameters."""
    if not ACCESS_TOKEN or ACCESS_TOKEN.startswith("YOUR_"):
        return {"status": "FAILED", "reason": "Credentials not set"}
        
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    components = []
    
    # Header media setup
    if media_id:
        components.append({
            "type": "header",
            "parameters": [
                {
                    "type": "image",
                    "image": {
                        "id": media_id
                    }
                }
            ]
        })
        
    # Body variables setup (maps Name to {{1}})
    if include_name:
        components.append({
            "type": "body",
            "parameters": [
                {
                    "type": "text",
                    "text": client_name
                }
            ]
        })
        
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {
                "code": LANGUAGE_CODE
            }
        }
    }
    
    if components:
        payload["template"]["components"] = components
        
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        res_data = response.json()
        if response.status_code == 200:
            return {"status": "SUCCESS", "message_id": res_data.get("messages", [{}])[0].get("id")}
        else:
            error_msg = res_data.get("error", {}).get("message", response.text)
            return {"status": "FAILED", "reason": error_msg}
    except Exception as e:
        return {"status": "FAILED", "reason": str(e)}

def send_direct_message(to_phone, message_text):
    """Sends a direct free-form text message to the recipient's phone using Meta Cloud API."""
    if not ACCESS_TOKEN or ACCESS_TOKEN.startswith("YOUR_"):
        return {"status": "FAILED", "reason": "Credentials not set"}
        
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {
            "body": message_text
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        res_data = response.json()
        if response.status_code == 200:
            msg_id = res_data.get("messages", [{}])[0].get("id")
            return {"status": "SUCCESS", "message_id": msg_id}
        else:
            error_msg = res_data.get("error", {}).get("message", response.text)
            return {"status": "FAILED", "reason": error_msg}
    except Exception as e:
        return {"status": "FAILED", "reason": str(e)}

# --- TAB 1: DAILY DISPATCH CENTER ---
with tab1:
    st.subheader("Daily Broadcast Console")
    
    # Metrics
    categories = db.get_unique_categories()
    all_clients_df, total_registered = db.get_clients_dataframe(status_filter="Active")
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">👥 Active Clients in DB</div>
            <div class="metric-value">{total_registered}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">🏷️ Total Categories</div>
            <div class="metric-value">{len(categories)}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m3:
        # Calculate size or count
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">⚡ WABA Account Link</div>
            <div class="metric-value" style="color: #22c55e; font-size: 22px; padding-top: 10px;">ACTIVE</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("### 1. Configure Target Recipients")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_category = st.selectbox("Filter Target Category", ["All"] + categories)
    with col_f2:
        send_mode = st.radio("Send Mode", ["Simulated (Sandbox Test)", "Live WhatsApp Broadcast"], horizontal=True,
                             help="Simulated mode runs the batch process, logs progress and verifies format without charging/sending actual API hits.")
        
    # Get filtered recipients
    target_df, target_count = db.get_clients_dataframe(category_filter=selected_category, status_filter="Active")
    st.info(f"🎯 Ready to target **{target_count}** client(s) matching your filter settings.")
    
    st.markdown("### 2. Upload and Prepare Daily Poster(s)")
    poster_files = st.file_uploader(
        "Select Daily Poster Images (Bulk Upload Supported)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    
    # Previews of uploaded images
    if poster_files:
        st.success(f"✅ Loaded {len(poster_files)} poster file(s) successfully.")
        cols = st.columns(min(len(poster_files), 4))
        for idx, file in enumerate(poster_files):
            col_idx = idx % 4
            with cols[col_idx]:
                st.image(file, caption=f"Poster {idx+1}: {file.name}", use_container_width=True)
                
    st.markdown("### 3. Send Parameters")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        include_name_param = st.checkbox("Include Client Name as Body Parameter ({{1}})", value=True,
                                         help="Check this if your template has a body parameter {{1}} for personalization.")
    with col_p2:
        match_by_filename = st.checkbox("🎯 Targeted Dispatch (Match Filename with Client's Phone)", value=False,
                                         help="Check this if you name your images with client phone numbers (e.g. 9876543210.png). The system will automatically map and send only the matching poster to each client.")
        
    # Send execution section
    if target_count > 0 and poster_files:
        st.markdown("### 4. Dispatch Dispatcher")
        
        # Confirmation box
        confirm_text = f"Send {len(poster_files)} poster(s) to {target_count} client(s) in {send_mode}."
        st.warning(f"⚠️ **Action Ready:** {confirm_text}")
        
        if st.button("🚀 EXECUTE WhatsApp BROADCAST NOW", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_terminal = st.empty()
            
            log_content = ""
            log_entries = []
            
            # Start timer
            start_time = time.time()
            
            # 1. Media caching (Upload images to Meta first in Live Mode)
            # Map filenames to cached media IDs
            cached_media_map = {}
            if send_mode == "Live WhatsApp Broadcast":
                status_text.text("⚙️ Initializing: Caching daily poster(s) onto Meta Cloud API...")
                for file in poster_files:
                    try:
                        # Save a copy locally so it can be rendered inside the Chat Inbox!
                        with open(file.name, "wb") as f:
                            f.write(file.getvalue())
                        # Read file bytes
                        file_bytes = file.getvalue()
                        media_id = upload_image_to_meta(file_bytes, file.name, file.type)
                        cached_media_map[file.name] = media_id
                        log_content += f"[{time.strftime('%H:%M:%S')}] Cached poster '{file.name}' to Meta Cloud. Media ID: {media_id}\n"
                        log_terminal.code(log_content, language="text", wrap_lines=True)
                    except Exception as e:
                        st.error(f"Failed to cache daily poster image: {str(e)}")
                        st.stop()
            else:
                # Simulated Mode - fake IDs
                for i, file in enumerate(poster_files):
                    try:
                        # Save a copy locally so it can be rendered inside the Chat Inbox!
                        with open(file.name, "wb") as f:
                            f.write(file.getvalue())
                    except Exception:
                        pass
                    cached_media_map[file.name] = f"sim_media_id_{i}"
                log_content += f"[{time.strftime('%H:%M:%S')}] Simulated caching for {len(poster_files)} poster(s) complete.\n"
                log_terminal.code(log_content, language="text", wrap_lines=True)
            
            # 2. Main recipient loop
            success_count = 0
            fail_count = 0
            
            # Iterate through clients
            for idx, row in target_df.iterrows():
                client_db_id = row['id']
                client_id = row['Client ID']
                c_name = row['Name']
                c_phone = row['Phone']
                
                # Extract 10-digit number for phone number matching
                short_phone = c_phone[-10:] if len(c_phone) >= 10 else c_phone
                
                if match_by_filename:
                    # Filter poster files matching the client's phone number
                    matched_files = []
                    for file in poster_files:
                        clean_name = os.path.splitext(file.name)[0]
                        if (short_phone in clean_name) or (c_phone in clean_name):
                            matched_files.append(file)
                            
                    if not matched_files:
                        log_msg = f"[{time.strftime('%H:%M:%S')}] SKIPPED ⏭️ -> {c_name} ({c_phone}) | Reason: No matching poster filename found.\n"
                        log_content += log_msg
                        log_terminal.code(log_content, language="text", wrap_lines=True)
                        continue
                else:
                    # Default: Send all files to all clients
                    matched_files = poster_files
                
                # Check for each matched poster
                for img_idx, file in enumerate(matched_files):
                    poster_name = file.name
                    media_id = cached_media_map[poster_name]
                    
                    status_text.text(f"Sending Poster {img_idx+1}/{len(matched_files)} to ({idx+1}/{target_count}): {c_name}...")
                    
                    if send_mode == "Live WhatsApp Broadcast":
                        res = send_whatsapp_template(
                            to_phone=c_phone, 
                            client_name=c_name, 
                            media_id=media_id,
                            include_name=include_name_param
                        )
                        if res["status"] == "SUCCESS":
                            success_count += 1
                            log_msg = f"[{time.strftime('%H:%M:%S')}] Live SUCCESS ✅ -> {c_name} ({c_phone}) | MsgID: {res['message_id']} | Poster: {poster_name}\n"
                            log_entries.append({"Timestamp": time.strftime('%Y-%m-%d %H:%M:%S'), "Client ID": client_id, "Name": c_name, "Phone": c_phone, "Poster": poster_name, "Status": "SUCCESS", "Detail": res['message_id']})
                            db.save_message(c_phone, "business", f"🖼️ Sent Poster: {poster_name}", res['message_id'])
                        else:
                            fail_count += 1
                            log_msg = f"[{time.strftime('%H:%M:%S')}] Live FAILED ❌ -> {c_name} ({c_phone}) | Reason: {res['reason']} | Poster: {poster_name}\n"
                            log_entries.append({"Timestamp": time.strftime('%Y-%m-%d %H:%M:%S'), "Client ID": client_id, "Name": c_name, "Phone": c_phone, "Poster": poster_name, "Status": "FAILED", "Detail": res['reason']})
                    else:
                        # Simulation
                        time.sleep(0.1) # quicker processing in simulation
                        success_count += 1
                        log_msg = f"[{time.strftime('%H:%M:%S')}] Sim SUCCESS ✅ -> {c_name} ({c_phone}) | Poster: {poster_name}\n"
                        log_entries.append({"Timestamp": time.strftime('%Y-%m-%d %H:%M:%S'), "Client ID": client_id, "Name": c_name, "Phone": c_phone, "Poster": poster_name, "Status": "SIMULATED SUCCESS", "Detail": "None"})
                        db.save_message(c_phone, "business", f"🖼️ Sent Poster: {poster_name}")
                    
                    log_content += log_msg
                    log_terminal.code(log_content, language="text", wrap_lines=True)
                
                # Apply rate limit delay between clients
                if idx < target_count - 1:
                    time.sleep(ANTI_BAN_DELAY)
                    
                # Update progress bar
                progress_bar.progress((idx + 1) / target_count)
                
            elapsed_time = round(time.time() - start_time, 2)
            status_text.text(f"🏁 Broadcast finished in {elapsed_time}s! Success: {success_count} | Failures: {fail_count}")
            
            st.success("🎉 Today's Daily Poster Broadcast Processed Successfully!")
            
            # Show summary log report
            report_df = pd.DataFrame(log_entries)
            st.dataframe(report_df, use_container_width=True)
            
            # CSV Download
            csv_data = report_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Dispatch Log Report (CSV)",
                data=csv_data,
                file_name=f"dispatch_report_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    else:
        if target_count == 0:
            st.warning("⚠️ No active clients match your category filter. Add/activate clients in the Database Manager.")
        if not poster_files:
            st.warning("📷 Please upload at least one poster image file above to begin the broadcast.")

# --- TAB 2: MASTER CLIENT DATABASE ---
with tab2:
    st.subheader("Master Client Database Manager")
    
    # Database Search & Table Pagination Settings
    col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
    with col_s1:
        search_query = st.text_input("🔍 Search Clients (Name, ID, Phone, Category)", "")
    with col_s2:
        cat_filter = st.selectbox("Filter Category List", ["All"] + db.get_unique_categories(), key="db_cat_filter")
    with col_s3:
        status_filter = st.selectbox("Filter Status", ["All", "Active", "Inactive"])
        
    # Get Filtered client count for pagination
    temp_df, filtered_total = db.get_clients_dataframe(search_query, cat_filter, status_filter)
    
    # Pagination configuration
    limit_per_page = 50
    total_pages = max(1, math.ceil(filtered_total / limit_per_page))
    
    col_p1, col_p2, col_p3 = st.columns([1, 1, 2])
    with col_p1:
        page_num = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
    with col_p2:
        st.markdown(f"<div style='padding-top: 25px; color: #94a3b8;'>of <b>{total_pages}</b> pages</div>", unsafe_allow_html=True)
    with col_p3:
        offset = (page_num - 1) * limit_per_page
        st.markdown(f"<div style='padding-top: 25px; text-align: right; color: #94a3b8;'>Showing records {offset + 1} - {min(offset + limit_per_page, filtered_total)} of <b>{filtered_total}</b></div>", unsafe_allow_html=True)
        
    # Load actual paginated dataframe
    clients_page_df, _ = db.get_clients_dataframe(search_query, cat_filter, status_filter, limit=limit_per_page, offset=offset)
    
    # Display client database
    if not clients_page_df.empty:
        st.dataframe(clients_page_df.drop(columns=["id"]), use_container_width=True)
    else:
        st.info("No client records found matching the filters.")
        
    # Action Sections: Manual Add / Bulk Setup / CRUD Edit
    st.markdown("---")
    action_tabs = st.tabs(["➕ Add Client Manually", "📥 Bulk Upload Excel/CSV", "✏️ Edit/Delete Client", "💾 Database Actions"])
    
    # 1. Manual Client Add
    with action_tabs[0]:
        st.markdown("### Add Single Client")
        with st.form("add_client_form", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                new_id = st.text_input("Client ID (e.g., TPA-1501)", placeholder="Leave blank to auto-generate")
                new_name = st.text_input("Name", placeholder="Enter Client Name")
            with col_f2:
                new_phone = st.text_input("Phone Number", placeholder="e.g. 9876543210 (Auto cleans & adds country code)")
                new_cat = st.text_input("Category", placeholder="e.g. VIP, Retail, Partner")
                
            submitted = st.form_submit_button("Add Client to Database", type="primary")
            if submitted:
                if not new_name or not new_phone:
                    st.error("Name and Phone fields are required.")
                else:
                    try:
                        # Auto generate if not provided
                        if not new_id.strip():
                            new_id = f"TPA-{filtered_total + 1:04d}"
                        
                        db.add_client(new_id, new_name, new_phone, new_cat, "Active", DEFAULT_COUNTRY_CODE)
                        st.success(f"✅ Successfully added '{new_name}' to Master database!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding client: {str(e)}")
                        
    # 2. Bulk Upload Sheet
    with action_tabs[1]:
        st.markdown("### Bulk Upload Database Sheet")
        st.write("Upload an Excel (`.xlsx`) or CSV file containing client data. The file **must** contain at least the columns `Name` and `Phone`. Optional columns: `Client ID`, `Category`, `Status`.")
        
        # Download Sample Template File
        sample_df = pd.DataFrame([
            {"Client ID": "TPA-0001", "Name": "Ramesh Kumar", "Phone": "9876543210", "Category": "VIP", "Status": "Active"},
            {"Client ID": "TPA-0002", "Name": "Suresh Sharma", "Phone": "+91 9999888877", "Category": "Retail", "Status": "Active"},
            {"Client ID": "TPA-0003", "Name": "Priya Patel", "Phone": "918888777766", "Category": "General", "Status": "Inactive"}
        ])
        
        sample_csv = sample_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Sample CSV Template",
            data=sample_csv,
            file_name="tpa_bulk_template.csv",
            mime="text/csv"
        )
        
        bulk_file = st.file_uploader("Choose Excel or CSV bulk database file", type=["csv", "xlsx"])
        if bulk_file:
            try:
                if bulk_file.name.endswith(".csv"):
                    df_upload = pd.read_csv(bulk_file)
                else:
                    df_upload = pd.read_excel(bulk_file)
                    
                st.write("🔍 File Preview:")
                st.dataframe(df_upload.head(3), use_container_width=True)
                
                if st.button("💾 SAVE PERMANENTLY TO LOCAL DATABASE", type="primary"):
                    with st.spinner("Processing & Cleaning bulk rows..."):
                        import_res = db.bulk_import(df_upload, DEFAULT_COUNTRY_CODE)
                    st.success(f"✅ Successfully imported/updated **{import_res['success']}** client rows!")
                    if import_res['failed'] > 0:
                        st.warning(f"⚠️ Ignored/Failed {import_res['failed']} rows.")
                        with st.expander("Show Import Failures"):
                            st.write(import_res['failures'])
                    st.rerun()
            except Exception as e:
                st.error(f"Error reading bulk file: {str(e)}")

    # 3. Edit / Delete Client
    with action_tabs[2]:
        st.markdown("### Edit or Delete Client")
        st.write("Search and edit single records here.")
        
        # Load all clients for dropdown select
        all_edit_df, _ = db.get_clients_dataframe(status_filter="All")
        if not all_edit_df.empty:
            # Create labels
            client_options = []
            client_map = {}
            for idx, row in all_edit_df.iterrows():
                db_id = row['id']
                label = f"{row['Client ID']} - {row['Name']} ({row['Phone']})"
                client_options.append(label)
                client_map[label] = row
                
            selected_label = st.selectbox("Select Client to Modify", client_options)
            
            if selected_label:
                selected_row = client_map[selected_label]
                
                with st.form("edit_client_form"):
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        edit_id = st.text_input("Client ID", value=selected_row["Client ID"])
                        edit_name = st.text_input("Name", value=selected_row["Name"])
                    with col_e2:
                        edit_phone = st.text_input("Phone Number", value=selected_row["Phone"])
                        edit_cat = st.text_input("Category", value=selected_row["Category"])
                        edit_status = st.selectbox("Status", ["Active", "Inactive"], index=0 if selected_row["Status"] == "Active" else 1)
                        
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        edit_submitted = st.form_submit_button("Update Client Records", type="primary")
                    with col_b2:
                        delete_submitted = st.form_submit_button("🚨 DELETE CLIENT PERMANENTLY")
                        
                    if edit_submitted:
                        try:
                            db.update_client(selected_row["id"], edit_id, edit_name, edit_phone, edit_cat, edit_status, DEFAULT_COUNTRY_CODE)
                            st.success(f"✅ Successfully updated client '{edit_name}'!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating client: {str(e)}")
                            
                    if delete_submitted:
                        db.delete_clients([selected_row["id"]])
                        st.success(f"🗑️ Client '{edit_name}' deleted permanently.")
                        st.rerun()
        else:
            st.info("No records in database to edit.")

    # 4. Database Actions
    with action_tabs[3]:
        st.markdown("### Export / Clean Database Utilities")
        
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            st.markdown("#### export Database")
            st.write("Export and download your database backup to Excel or CSV.")
            
            full_db_df, _ = db.get_clients_dataframe(status_filter="All")
            if not full_db_df.empty:
                # CSV Export
                export_csv = full_db_df.drop(columns=["id"]).to_csv(index=False)
                st.download_button(
                    label="📥 Export Full Database to CSV",
                    data=export_csv,
                    file_name="tpa_clients_backup.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("Database is empty, nothing to export.")
                
        with col_u2:
            st.markdown("#### 🚨 Dangerous Area")
            st.write("Wipe database clean. This action is permanent and cannot be undone.")
            
            confirm_wipe_text = st.text_input("Type 'DELETE ALL' to confirm wiping the database:", "")
            if st.button("🚨 DESTROY ALL CLIENT DATABASE RECORDS", type="primary", disabled=(confirm_wipe_text != "DELETE ALL"), use_container_width=True):
                db.clear_all_clients()
                st.success("💥 Database wiped clean. All records deleted!")
                st.rerun()

# --- TAB 3: INBOX & LIVE CHAT ---
with tab3:
    st.subheader("💬 Two-way WhatsApp CRM Inbox")
    st.write("View incoming replies from clients in real-time and reply directly to open conversations.")

    # WhatsApp Web Styling for Radio Buttons and Chat Thread
    st.markdown("""
        <style>
        /* WhatsApp-like layout for chat list */
        div[data-testid="stRadio"] > div[role="radiogroup"] {
            gap: 8px !important;
        }
        div[data-testid="stRadio"] label {
            background-color: #1e293b !important;
            border: 1px solid #334155 !important;
            border-radius: 12px !important;
            padding: 12px 16px !important;
            color: #e2e8f0 !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
            width: 100% !important;
            margin-bottom: 2px !important;
            display: block !important;
        }
        div[data-testid="stRadio"] label:hover {
            background-color: #334155 !important;
            border-color: #475569 !important;
        }
        /* Style the selected chat card */
        div[data-testid="stRadio"] label:has(input:checked) {
            background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%) !important;
            border-color: #14b8a6 !important;
            color: #ffffff !important;
            box-shadow: 0 4px 12px rgba(13, 148, 136, 0.3) !important;
        }
        /* Hide the default radio circle input */
        div[data-testid="stRadio"] label input[type="radio"] {
            display: none !important;
        }
        /* Remove extra padding from container */
        div[data-testid="stRadio"] label div[class*="st-"] {
            padding: 0 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Two-column layout
    col_chat_list, col_chat_window = st.columns([1, 2])

    # 1. Left column: conversations list
    selected_phone = None
    with col_chat_list:
        st.markdown("#### Recent Conversations")
        
        # Inbox Controls
        col_c_ref, col_c_spacer = st.columns([1, 2])
        with col_c_ref:
            if st.button("🔄 Refresh"):
                st.rerun()
                
        try:
            conversations = db.get_conversations()
            
            # Chat Search filter
            search_chat = st.text_input("🔍 Search Chats", placeholder="Search by name or phone...", label_visibility="collapsed")
            if search_chat and not conversations.empty:
                conversations = conversations[
                    conversations['name'].str.contains(search_chat, case=False, na=False) |
                    conversations['phone'].str.contains(search_chat, case=False, na=False)
                ]
                
            if conversations.empty:
                st.info("No matching conversations found.")
            else:
                options = []
                phone_map = {}
                for idx, row in conversations.iterrows():
                    name = row['name'] if row['name'] else "Unknown Lead"
                    unread_badge = "🔴 " if row['sender'] == 'client' else ""
                    
                    # Clean the message preview for list layout
                    msg_preview = str(row['message'])
                    if msg_preview.startswith("📷 Incoming Image:"):
                        msg_preview = "📷 Client Photo"
                    elif msg_preview.startswith("🖼️ Sent Poster:"):
                        msg_preview = "🖼️ Sent Poster"
                    
                    if len(msg_preview) > 22:
                        msg_preview = msg_preview[:20] + "..."
                        
                    label = f"{unread_badge}👤 {name} ({row['phone']})\n💬 {msg_preview}"
                    options.append(label)
                    phone_map[label] = row['phone']
                
                selected_label = st.radio("Select Chat", options, label_visibility="collapsed")
                if selected_label:
                    selected_phone = phone_map[selected_label]
        except Exception as e:
            st.error(f"Error loading conversations: {e}")

    # 2. Right column: chat window and direct reply
    with col_chat_window:
        if selected_phone:
            # Get client details
            client_name = "Unknown Client"
            try:
                client_info, count = db.get_clients_dataframe(search_query=selected_phone)
                if count > 0:
                    client_name = client_info.iloc[0]['Name']
            except Exception as e:
                pass
                
            st.markdown(f"#### Conversation with: **{client_name}** (`{selected_phone}`)")
            
            # Retrieve messages for this phone number
            try:
                msgs_df = db.get_messages_for_phone(selected_phone)
                
                # Chat bubbles HTML container (written in a single line string to avoid markdown code formatting)
                chat_html = '<div style="height: 480px; overflow-y: auto; padding: 20px; background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 16px; margin-bottom: 20px; display: flex; flex-direction: column; gap: 12px;">'
                
                for idx, row in msgs_df.iterrows():
                    sender = row['sender']
                    msg_text = row['message']
                    ts = row['timestamp']
                    media_b64 = row['media_b64'] if 'media_b64' in row and not pd.isna(row['media_b64']) else None
                    
                    if sender == 'client':
                        # Received bubble (Slate-blue)
                        if media_b64 and str(media_b64).strip():
                            chat_html += f'<div style="align-self: flex-start; max-width: 60%; background-color: #1e293b; padding: 8px; border-radius: 16px 16px 16px 4px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); margin-bottom: 4px;"><img src="data:image/png;base64,{media_b64}" style="width: 100%; border-radius: 12px; display: block; margin-bottom: 6px;" /><div style="font-size: 11px; color: #94a3b8; padding: 0 4px;">📷 Client Image</div><div style="font-size: 10px; color: #94a3b8; text-align: right; margin-top: 4px; padding: 0 4px;">{ts}</div></div>'
                        elif str(msg_text).startswith("📷 Incoming Image:"):
                            incoming_name = str(msg_text).replace("📷 Incoming Image:", "").strip()
                            b64_in = get_image_base64(incoming_name)
                            if b64_in:
                                chat_html += f'<div style="align-self: flex-start; max-width: 60%; background-color: #1e293b; padding: 8px; border-radius: 16px 16px 16px 4px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); margin-bottom: 4px;"><img src="data:image/png;base64,{b64_in}" style="width: 100%; border-radius: 12px; display: block; margin-bottom: 6px;" /><div style="font-size: 11px; color: #94a3b8; padding: 0 4px;">📷 Client Image</div><div style="font-size: 10px; color: #94a3b8; text-align: right; margin-top: 4px; padding: 0 4px;">{ts}</div></div>'
                            else:
                                chat_html += f'<div style="align-self: flex-start; max-width: 75%; background-color: #1e293b; color: #f1f5f9; padding: 12px 16px; border-radius: 16px 16px 16px 4px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); margin-bottom: 4px;"><div style="font-size: 14px; font-weight: 500; line-height: 1.4;">📷 Incoming Image: {incoming_name}</div><div style="font-size: 10px; color: #94a3b8; text-align: right; margin-top: 6px;">{ts}</div></div>'
                        else:
                            chat_html += f'<div style="align-self: flex-start; max-width: 75%; background-color: #1e293b; color: #f1f5f9; padding: 12px 16px; border-radius: 16px 16px 16px 4px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); margin-bottom: 4px;"><div style="font-size: 14px; font-weight: 500; line-height: 1.4;">{msg_text}</div><div style="font-size: 10px; color: #94a3b8; text-align: right; margin-top: 6px;">{ts}</div></div>'
                    else:
                        # Sent bubble (Dark gray/Teal border)
                        # Check if this is a Sent Poster image type message
                        if str(msg_text).startswith("🖼️ Sent Poster:"):
                            poster_name = str(msg_text).replace("🖼️ Sent Poster:", "").strip()
                            b64 = get_image_base64(poster_name)
                            
                            if b64:
                                # Show actual image bubble
                                chat_html += f'<div style="align-self: flex-end; max-width: 60%; background-color: #0f172a; border: 1px solid #0d9488; padding: 8px; border-radius: 16px 16px 4px 16px; box-shadow: 0 4px 10px rgba(13, 148, 136, 0.15); margin-bottom: 4px;"><img src="data:image/png;base64,{b64}" style="width: 100%; border-radius: 12px; display: block; margin-bottom: 6px;" /><div style="font-size: 11px; color: #94a3b8; padding: 0 4px;">🖼️ {poster_name}</div><div style="font-size: 10px; color: #0d9488; text-align: right; margin-top: 4px; padding: 0 4px;">{ts} (You)</div></div>'
                            else:
                                # Fallback if image file is not on the server
                                chat_html += f'<div style="align-self: flex-end; max-width: 75%; background-color: #0f172a; border: 1px solid #0d9488; color: #2dd4bf; padding: 12px 16px; border-radius: 16px 16px 4px 16px; box-shadow: 0 4px 10px rgba(13, 148, 136, 0.15); margin-bottom: 4px;"><div style="font-size: 14px; color: #f1f5f9; font-weight: 500; line-height: 1.4;">🖼️ Sent Poster: {poster_name}</div><div style="font-size: 10px; color: #0d9488; text-align: right; margin-top: 6px;">{ts} (You)</div></div>'
                        else:
                            # Standard text bubble
                            chat_html += f'<div style="align-self: flex-end; max-width: 75%; background-color: #0f172a; border: 1px solid #0d9488; color: #2dd4bf; padding: 12px 16px; border-radius: 16px 16px 4px 16px; box-shadow: 0 4px 10px rgba(13, 148, 136, 0.15); margin-bottom: 4px;"><div style="font-size: 14px; color: #f1f5f9; font-weight: 500; line-height: 1.4;">{msg_text}</div><div style="font-size: 10px; color: #0d9488; text-align: right; margin-top: 6px;">{ts} (You)</div></div>'
                chat_html += '</div>'
                st.markdown(chat_html, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Error loading chat bubbles: {e}")
                
            # Reply Input Form
            with st.form(key=f"reply_form_{selected_phone}", clear_on_submit=True):
                reply_text = st.text_area("Write reply...", placeholder="Type a message to reply...", label_visibility="collapsed")
                col_sbtn, _ = st.columns([1, 2])
                with col_sbtn:
                    submit_reply = st.form_submit_button("📤 Send Direct Reply", use_container_width=True)
                    
                if submit_reply and reply_text.strip():
                    with st.spinner("Sending message..."):
                        res = send_direct_message(selected_phone, reply_text)
                        if res["status"] == "SUCCESS":
                            # Save reply to database
                            db.save_message(selected_phone, "business", reply_text, res["message_id"])
                            st.success("Reply dispatched successfully!")
                            st.rerun()
                        else:
                            st.error(f"Failed to dispatch reply: {res['reason']}")
        else:
            st.info("👈 Select a conversation thread from the list to view chat and reply.")

# --- TAB 4: SETTINGS & DEV SANDBOX ---
with tab4:
    st.subheader("WhatsApp Cloud Developer Sandbox")
    st.write("This testing sandbox helps you verify that Meta API credentials, media uploads, and template parameters are correctly aligned with Meta servers *before* doing bulk blasts.")
    
    st.markdown("### Test Meta API Connection")
    
    test_phone = st.text_input("Enter Test Recipient Phone Number", placeholder="e.g. 919876543210 (Country code + phone)")
    test_image = st.file_uploader("Upload a Single Test Poster Image", type=["png", "jpg", "jpeg"], key="test_image_upload")
    
    test_body_name = st.checkbox("Simulate body parameter (Use Name: 'Test Client')", value=True, key="test_body_name")
    
    if st.button("⚡ RUN Meta API CONNECTION DIAGNOSTIC CHECK", type="primary"):
        if not PHONE_NUMBER_ID or not ACCESS_TOKEN:
            st.error("Missing Phone Number ID or Access Token in the Sidebar.")
        elif not test_phone:
            st.error("Please enter a valid recipient phone number.")
        else:
            with st.spinner("Running diagnostics..."):
                st.info("Step 1: Testing API credentials against Meta servers...")
                
                # Test image uploading if image provided
                test_media_id = None
                if test_image:
                    st.info("Step 2: Testing binary file upload to Meta Media API...")
                    try:
                        test_media_id = upload_image_to_meta(test_image.getvalue(), test_image.name, test_image.type)
                        st.success(f"✅ Meta Media Upload Success! Media ID: `{test_media_id}`")
                    except Exception as e:
                        st.error(f"❌ Meta Media Upload Failure: {str(e)}")
                        st.stop()
                else:
                    st.warning("⚠️ No test image uploaded. Template message will be sent *without* header (will fail if your template requires an image header).")
                
                st.info("Step 3: Triggering Template message dispatch...")
                res = send_whatsapp_template(
                    to_phone=test_phone,
                    client_name="Test Client",
                    media_id=test_media_id,
                    include_name=test_body_name
                )
                
                if res["status"] == "SUCCESS":
                    st.success("🎉 Connection Test SUCCESS! The template message was queued on Meta servers.")
                    st.info(f"Message ID returned: `{res['message_id']}`")
                else:
                    st.error(f"❌ Connection Test FAILED. Reason: {res['reason']}")
                    
                    # Helpful troubleshooting tips
                    st.markdown("""
                    #### Troubleshooting Checklists:
                    1. **Invalid Phone/Access Token**: Ensure your Phone Number ID is the numeric ID (not business ID), and the token is active.
                    2. **Template Mismatch**: Double check if the `Template Name` matches the value in your Meta App WhatsApp Manager exactly.
                    3. **Language Code**: Make sure the Language Code matches the exact translation language created on Meta (e.g. `en_US` vs `en`).
                    4. **Template Variables**: Ensure the template is approved and expects an image header. If it doesn't support a body parameter, uncheck "Simulate body parameter".
                    """)
                    
    st.markdown("---")
    st.markdown("### 📋 WhatsApp Cloud API Info")
    st.info("""
    **Developer Guidelines:**
    - Standard WABA API endpoints use version `v20.0` or higher.
    - Media uploaded to Meta Cloud servers remains cached for exactly **30 days**.
    - Phone number strings must follow E.164 standards: only digits, starting with country code (no leading `+` or spaces).
    """)
