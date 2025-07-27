from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import uvicorn
import base64
import json
import os
from dotenv import load_dotenv

app = FastAPI()

# Loading environment variable and initiating it
load_dotenv()
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER') # Your Twilio number
TO_PHONE_NUMBER = os.environ.get('TO_PHONE_NUMBER') # The number to call

# Initialize Twilio Client
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    print("WARNING: Twilio credentials not set as environment variables. Outbound calling will not work.")
    client = None

# --- Existing /voice webhook (for incoming calls, or for Twilio to call back to) ---
@app.post("/voice")
async def voice_webhook():
    # This is the initial webhook from Twilio when a call comes in
    # OR, it's the URL Twilio calls when you initiate an outbound call to handle the response
    response = VoiceResponse()
    # Replace YOUR_NGROK_URL with your actual ngrok URL.
    # This URL must be accessible by Twilio.
    # When Twilio calls this webhook, it then initiates the WebSocket stream back to YOUR_NGROK_URL/ws
    response.start().stream(url="https://echoship.onrender.com/ws")
    response.say("Hello! This is a call initiated by your FastAPI server. Please speak now.") # Initial greeting
    return Response(content=str(response), media_type="application/xml")

# --- New Endpoint to Initiate Outbound Call ---
@app.post("/make-call")
async def make_call():
    if not client:
        raise HTTPException(status_code=500, detail="Twilio client not initialized. Check environment variables.")
    if not TWILIO_PHONE_NUMBER or not TO_PHONE_NUMBER:
        raise HTTPException(status_code=500, detail="TWILIO_PHONE_NUMBER or TO_PHONE_NUMBER not set as environment variables.")

    try:
        # Replace YOUR_NGROK_URL with your actual ngrok URL.
        # This is the URL Twilio will hit once the call connects,
        # which will then direct to your /voice webhook.
        call = client.calls.create(
            to=TO_PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            url="https://echoship.onrender.com/voice" # Twilio will request this URL to get TwiML instructions
        )
        print(f"Call initiated! SID: {call.sid}")
        return {"message": "Call initiated successfully!", "call_sid": call.sid}
    except Exception as e:
        print(f"Error initiating call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {e}")

# --- Existing WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection established with Twilio!")
    try:
        while True:
            message = await websocket.receive_text()
            payload = json.loads(message)

            if payload["event"] == "start":
                print(f"Call started. SID: {payload['streamSid']}")
            elif payload["event"] == "media":
                audio_data = base64.b64decode(payload["media"]["payload"])
                print(f"Received audio chunk of length: {len(audio_data)} bytes")
                # You'll process this audio data with STT later
            elif payload["event"] == "stop":
                print("Call stopped.")
                break
            else:
                print(f"Received unknown event: {payload['event']}")

    except WebSocketDisconnect:
        print("WebSocket disconnected.")
    except Exception as e:
        print(f"Error in WebSocket: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)