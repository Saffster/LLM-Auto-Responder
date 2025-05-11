import imaplib
import smtplib
import email
from email.message import EmailMessage
from dotenv import load_dotenv
import os
import time
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

# === GPT-4 Email Reply Generator ===
def generate_reply(request_text):
    prompt = (
        "You are an AI assistant replying to business emails. "
        "Generate a complete, helpful, and professional email reply based on the content below. "
        "If details are missing, make intelligent assumptions and provide a confident, informative response. "
        "Sign off as Krisha Khatri, Digital Marketing Analyst.\n\n"
        f"Email content:\n\"\"\"\n{request_text.strip()}\n\"\"\""
    )

    response = client.chat.completions.create(
        model="gpt-4",
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

            ai_reply = generate_reply(body)

            reply = EmailMessage()
            reply['From'] = EMAIL_ACCOUNT
            reply['To'] = from_addr
            reply['Subject'] = f"Re: {subject}"
            reply.set_content(ai_reply)

            with smtplib.SMTP_SSL(SMTP_SERVER, 465) as smtp:
                smtp.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
                smtp.send_message(reply)

            print(f"✅ Replied to {from_addr} with GPT-4 response.")

        mail.logout()

    except Exception as e:
        print(f"⚠️ Error occurred: {e}")

    time.sleep(5)
