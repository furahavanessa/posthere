# app.py — Production-ready version for Render + Supabase (PostgreSQL)

import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from dotenv import load_dotenv
import random
from main import save_report, find_secure_matches

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Twilio configuration
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# Initialize Twilio client (only if credentials exist)
client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# In-memory sessions (for MVP – in production consider Redis or database)
user_sessions = {}

def send_whatsapp(to_number, body):
    """Send outbound WhatsApp message via Twilio"""
    if not client:
        print(f"[DRY RUN] Would send to {to_number}: {body[:100]}...")
        return False
    try:
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=body,
            to=to_number
        )
        print(f"Outbound message sent to {to_number} - SID: {message.sid}")
        return True
    except Exception as e:
        print(f"Twilio outbound error: {e}")
        return False


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """Main Twilio webhook endpoint"""
    incoming_msg = (request.values.get("Body") or "").strip()
    from_number = request.values.get("From")
    msg_lower = incoming_msg.lower()

    resp = MessagingResponse()
    reply = resp.message()

    print(f"[{from_number}] Received: {incoming_msg!r}")

    # Quick status check command
    if msg_lower in ["status", "statut", "3"]:
        reply.body("La fonction de statut détaillé arrive bientôt.\nPour l'instant, recommencez avec 1 ou 2.")
        return str(resp)

    # New conversation
    if from_number not in user_sessions:
        user_sessions[from_number] = {"step": "start", "data": {}, "status": ""}
        reply.body(
            "⚖️ *Goma Lost & Found – Signalement sécurisé*\n\n"
            "1 = J'ai **perdu** quelque chose\n"
            "2 = J'ai **trouvé** quelque chose\n\n"
            "Répondez avec 1 ou 2\n"
            "(ou 'status' pour vérifier plus tard)"
        )
        return str(resp)

    state = user_sessions[from_number]

    # Handle start choice
    if state["step"] == "start":
        if incoming_msg == "1":
            state["status"] = "lost"
        elif incoming_msg == "2":
            state["status"] = "found"
        else:
            reply.body("Veuillez répondre avec 1 ou 2 uniquement.")
            return str(resp)

        state["step"] = "ask_item"
        question = "Quel objet avez-vous **perdu** ?" if state["status"] == "lost" else "Quel objet avez-vous **trouvé** ?"
        reply.body(question)
        return str(resp)

    # Item name
    if state["step"] == "ask_item":
        state["data"]["item"] = incoming_msg.strip()
        state["step"] = "ask_specs"
        reply.body("Description détaillée (marque, couleur, état, rayures, particularités…) :")
        return str(resp)

    # Description / specs
    if state["step"] == "ask_specs":
        state["data"]["specs"] = incoming_msg.strip()
        state["step"] = "ask_location"
        reply.body("Où exactement à Goma ? (quartier, marché, rue, point de repère précis) :")
        return str(resp)

    # Location
    if state["step"] == "ask_location":
        state["data"]["location"] = incoming_msg.strip()
        state["step"] = "ask_secret1"
        txt = "un détail que **seul le vrai propriétaire** connaît" if state["status"] == "lost" else "un détail que le propriétaire devra donner pour prouver son identité"
        reply.body(f"🔐 Sécurité – Détail 1/2\nDonnez {txt} :")
        return str(resp)

    # Secret 1
    if state["step"] == "ask_secret1":
        state["data"]["secret1"] = incoming_msg.strip().lower()
        state["step"] = "ask_secret2"
        reply.body("🔐 Sécurité – Détail 2/2\nUn autre détail très spécifique et unique :")
        return str(resp)

    # Secret 2 → save & match (if lost)
    if state["step"] == "ask_secret2":
        state["data"]["secret2"] = incoming_msg.strip().lower()

        # Save the report
        save_report(state["data"], from_number, state["status"])

        if state["status"] == "lost":
            matches = find_secure_matches(
                state["data"]["item"],
                state["data"]["location"],
                state["data"]["secret1"],
                state["data"]["secret2"],
                "found"
            )

            if matches:
                match = matches[0]  # take first strong match
                code = str(random.randint(100000, 999999))

                # Mark as claimed (you may want to update this in main.py if needed)
                send_whatsapp(
                    match["phone"],
                    f"Quelqu’un recherche un objet correspondant au vôtre ({match['item_name']}).\n"
                    f"Si vous pensez que c’est le même, répondez :\n"
                    f"APPROUVER {code}"
                )

                reply.body(
                    "✅ Correspondance probable trouvée !\n"
                    "Nous avons contacté le déposant pour confirmation.\n"
                    "Vous serez averti(e) si c’est validé.\n"
                    "Tapez 'status' plus tard pour suivre."
                )
            else:
                reply.body(
                    "Signalement enregistré.\n"
                    "Pas de correspondance immédiate. Nous vous contacterons si un match apparaît."
                )
        else:
            reply.body(
                "✅ Merci ! Votre objet trouvé est maintenant signalé.\n"
                "Si le propriétaire se manifeste avec les bons détails, nous vous mettrons en contact."
            )

        # End session
        del user_sessions[from_number]
        return str(resp)

    # Fallback
    reply.body("Désolé, je ne comprends pas cette étape.\nRecommencez en envoyant 1 ou 2.")
    return str(resp)


if __name__ == "__main__":
    # For local development only
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)