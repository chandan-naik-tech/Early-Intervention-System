import os
def send(phone, text, channel="sms"):
    sid, tok = os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN")
    if sid and tok:
        try:
            from twilio.rest import Client
            c = Client(sid, tok)
            if channel == "whatsapp":
                c.messages.create(from_="whatsapp:" + os.getenv("TWILIO_WHATSAPP_FROM", ""), to="whatsapp:" + phone, body=text)
            else:
                c.messages.create(from_=os.getenv("TWILIO_SMS_FROM", ""), to=phone, body=text)
            return "sent"
        except Exception as e:
            return f"failed: {e}"[:120]
    print(f"[SIMULATED {channel.upper()} to {phone}] {text}")
    return "simulated (no Twilio keys)"
