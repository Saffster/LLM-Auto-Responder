import imaplib
import smtplib
import email
from email.message import EmailMessage
from dotenv import load_dotenv
import os
import time
import requests
from openai import OpenAI

# === Load Environment Variables ===
load_dotenv()

IMAP_SERVER = 'imap.gmail.com'
SMTP_SERVER = 'smtp.gmail.com'

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ✅ Initialize OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)

# === Flight API Fetcher ===
def get_flight_details():
    url = "https://neoflightapi.dev.futuretravelplatform.com/search/options"
    headers = {"Content-Type": "application/json"}
    payload = {
        "Adult": 1,
        "Child": 0,
        "TripType": "1",
        "TripTypeKey": "ONEWAY",
        "AffiliateId": "2412310726013014383",
        "OrgId": "2212051818221653784",
        "Segments": [
            {
                "Origin": "CAI",
                "Destination": "JED",
                "Date": "27 May 2025",
                "Class": "Y"
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            flight = data[0]
            return {
                "flight_number": flight.get("fnm"),
                "origin": flight.get("dac"),
                "destination": flight.get("adc"),
                "departure_time": flight.get("dti"),
                "arrival_time": flight.get("ati"),
                "airline": flight.get("mcc"),
                "price": flight.get("act", ["?"])[0]
            }
        else:
            return None
    except Exception as e:
        return {"error": str(e)}

# === GPT-4 Email Reply Generator ===
def generate_reply(request_text, flight_info=None):
    prompt = (
        "You are an AI assistant replying to business emails. "
        "Generate a complete, helpful, and professional reply based on the content below. "
        "If details are missing, make intelligent assumptions and provide a confident response.\n\n"
        f"Email content:\n\"\"\"\n{request_text.strip()}\n\"\"\""
    )

    if flight_info and "flight_number" in flight_info:
        prompt += (
            "\n\nFlight details (from live system):\n"
            f"- Flight: {flight_info['flight_number']} ({flight_info['airline']})\n"
            f"- From: {flight_info['origin']} to {flight_info['destination']}\n"
            f"- Departs at: {flight_info['departure_time']} and arrives at: {flight_info['arrival_time']}\n"
            f"- Price: ${flight_info['price']} USD"
        )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a polite and proactive email assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content.strip()

# === Infinite Loop to Check Emails Every 5 Seconds ===
while True:
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select('inbox')

        status, messages = mail.search(None, '(UNSEEN)')
        email_ids = messages[0].split()

        if email_ids:
            print(f"📨 {len(email_ids)} unread emails found.")
        else:
            print("✅ No new emails. Checking again in 5 seconds...")

        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, '(RFC822)')
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            from_addr = email.utils.parseaddr(msg['From'])[1]
            subject = msg['Subject'] or "No Subject"
            body = ""

            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain' and 'attachment' not in str(part.get("Content-Disposition", "")):
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()

            print(f"✉️ Reading email from {from_addr} with subject: {subject}")

            # Fetch flight info (can add filters later)
            flight_info = get_flight_details()

            # Generate AI-powered reply
            ai_reply = generate_reply(body, flight_info)

            reply = EmailMessage()
            reply['From'] = EMAIL_ACCOUNT
            reply['To'] = from_addr
            reply['Subject'] = f"Re: {subject}"
            reply.set_content(ai_reply)

            with smtplib.SMTP_SSL(SMTP_SERVER, 465) as smtp:
                smtp.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
                smtp.send_message(reply)

            print(f"✅ Replied to {from_addr} with GPT-4 + flight data response.")

        mail.logout()

    except Exception as e:
        print(f"⚠️ Error occurred: {e}")

    time.sleep(5)
