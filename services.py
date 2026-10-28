"""External connectors. Never silently claim email or voice succeeded."""
import asyncio
import os
import smtplib
import tempfile
from email.message import EmailMessage

VOICE_IDS = {
    'English': 'en-IN-NeerjaNeural',
    'Tamil': 'ta-IN-PallaviNeural',
    'Hindi': 'hi-IN-SwaraNeural',
}


def voice_mp3(text: str, language: str) -> bytes:
    """Uses online Edge neural TTS service; no local audio file is retained."""
    import edge_tts

    voice = VOICE_IDS.get(language, VOICE_IDS['English'])

    async def _generate(output_path: str) -> None:
        comm = edge_tts.Communicate(text=text, voice=voice, rate='-5%')
        await comm.save(output_path)

    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        output = f.name
    try:
        # edge-tts is fully async; run it inside a dedicated event loop.
        # Streamlit runs in a thread that may already have a running loop
        # (Python 3.10+ with asyncio.get_event_loop policy changes), so we
        # always create a fresh loop to be safe.
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_generate(output))
        finally:
            loop.close()

        with open(output, 'rb') as f:
            data = f.read()
        if not data:
            raise RuntimeError('TTS produced no audio bytes.')
        return data
    finally:
        try:
            os.remove(output)
        except OSError:
            pass


def send_email(recipient, subject, body, username, password, host='smtp.gmail.com', port=465):
    """Real SMTP send; throws on failure. Caller logs event only on success."""
    if not username or not password:
        raise ValueError('SMTP email credentials are not set. Use preview mode first.')
    if '@' not in recipient:
        raise ValueError('Recipient email looks invalid.')
    message = EmailMessage()
    message['From'] = username
    message['To'] = recipient
    message['Subject'] = subject
    message.set_content(body)
    with smtplib.SMTP_SSL(host, int(port), timeout=20) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)
