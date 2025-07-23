import imaplib
import smtplib
import email
from email.message import EmailMessage
from dotenv import load_dotenv
import os
import time
import json
import requests
from langchain_openai import ChatOpenAI
from flight_info_extractor import validate_extraction, format_flight_results

# === Load Environment Variables ===
load_dotenv()

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

AFFILIATE_ID = os.getenv("AFFILIATE_ID")
ORG_ID = os.getenv("ORG_ID")
ADULT = int(os.getenv("ADULT", "1"))
CHILD = int(os.getenv("CHILD", "0"))
TRIP_TYPE = os.getenv("TRIP_TYPE", "1").strip()

llm = ChatOpenAI(model="gpt-4", temperature=0.3)

# === Logger ===
def log(msg):
    with open("logs.txt", "a") as f:
        f.write(f"{time.ctime()} | {msg}\n")

# === Email Handling ===
def fetch_unread_emails():
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select("inbox")
    result, data = mail.search(None, '(UNSEEN)')
    if result != "OK":
        return []

    emails = []
    for num in data[0].split():
        result, data = mail.fetch(num, '(RFC822)')
        if result == "OK":
            raw_email = data[0][1]
            message = email.message_from_bytes(raw_email)
            sender = message["From"]
            subject = message["Subject"]
            body = ""
            if message.is_multipart():
                for part in message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = message.get_payload(decode=True).decode()
            emails.append((sender, subject, body))
    return emails

def send_reply(to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = f"Re: {subject}"
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = to_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.send_message(msg)

# === Extract Flight Request from Email ===
def extract_flight_details(email_text: str) -> dict:
    query = f"""
You are a helpful travel assistant.

Extract flight search information from the following message:
\"\"\"{email_text}\"\"\"

Return a JSON object with the following keys:
- "origin": IATA airport code of the departure city (e.g., "SYD")
- "destination": IATA airport code of the arrival city (e.g., "DXB")
- "date": Departure date in the format "DD MMM YYYY" (e.g., "27 Jul 2025")

Make sure to:
- Convert city names to correct IATA codes
- Convert date phrases like "next Friday" into the correct date format

Example Input:
"Looking to fly from Sydney to Dubai next Friday"

Example Output:
{{
  "origin": "SYD",
  "destination": "DXB",
  "date": "26 Jul 2025"
}}

Only return the JSON object.
"""
    response = llm.invoke(query)
    try:
        json_str = response.content[response.content.find("{"):]
        return json.loads(json_str)
    except Exception:
        return {}

# === Call Flight API ===
def get_flight_info_dynamic(origin, destination, date):
    url = "https://neoflightapi.dev.futuretravelplatform.com/search/options"
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "PostmanRuntime/7.44.0",
        "org_id": ORG_ID,
        "secretkey": os.getenv("FLIGHT_SECRET_KEY")
    }
    payload = {
        "Adult": ADULT,
        "Child": CHILD,
        "TripType": TRIP_TYPE,
        "AffiliateId": AFFILIATE_ID,
        "OrgId": ORG_ID,
        "Segments": [{
            "Origin": origin,
            "Destination": destination,
            "Date": date,
            "Class": "Y"
        }]
    }

    try:
        print("Calling API with payload:", json.dumps(payload, indent=2))
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        print("API raw response:", response.text[:1000])
        return response.json().get("fop", [])[:5]
    except Exception as e:
        print("API call failed:", e)
        return []

# === Travel Package Prompt (Optional) ===
def get_travel_package_req_template():
    template = """<PASTE YOUR PROVIDED TRAVEL PACKAGE TEMPLATE HERE>"""
    return template

# === Main Loop ===
if __name__ == "__main__":
    print("Starting LLM Email AutoResponder...")
    log("System started")

    while True:
        print("Checking for unread emails...")
        emails = fetch_unread_emails()
        print(f"Found {len(emails)} unread email(s).")
        log(f"Found {len(emails)} unread email(s).")

        for sender, subject, content in emails:
            sender_email = sender.lower().split()[-1].strip("<>")
            print(f"Responding to: {sender_email} | Subject: {subject}")
            log(f"Responding to: {sender_email} | Subject: {subject}")

            try:
                extracted = extract_flight_details(content)

                validation_msg = validate_extraction(extracted)
                if "Missing" in validation_msg:
                    send_reply(sender_email, subject, validation_msg)
                    log(f"Missing data: {validation_msg}")
                    continue

                flights = get_flight_info_dynamic(
                    extracted['origin'], extracted['destination'], extracted['date']
                )
                reply = format_flight_results(flights)
                send_reply(sender_email, subject, reply)
                log(f"Replied to {sender_email}")
            except Exception as e:
                error_msg = f"Error responding to {sender_email}: {e}"
                print(error_msg)
                log(error_msg)

        time.sleep(60)  # Reduced polling frequency