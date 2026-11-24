
import os
import tempfile
import secrets
import edge_tts

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

app = FastAPI(
    title="Chinese TTS API",
    description="Chinese Mandarin Text-to-Speech MP3 Generator",
    version="1.0.0"
)

# Supported Mandarin voices
ALLOWED_VOICES = [
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-YunyangNeural"
]


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice: str = "zh-CN-XiaoxiaoNeural"
    speed: float = Field(default=0.85, ge=0.5, le=1.5)


@app.get("/")
async def home():
    return {
        "service": "Chinese TTS API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/voices")
async def voices():
    return {"voices": ALLOWED_VOICES}


@app.post("/tts")
async def generate_tts(
    request: TTSRequest,
    x_api_key: str = Header(default="")
):
    # Check API secret
    api_secret = os.environ.get("API_SECRET")

    if not api_secret:
        raise HTTPException(
            status_code=503,
            detail="API_SECRET is not configured"
        )

    if not secrets.compare_digest(x_api_key, api_secret):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    # Validate voice
    if request.voice not in ALLOWED_VOICES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported Mandarin voice"
        )

    text = request.text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty"
        )

    # Convert speed to Edge TTS rate
    percentage = round((request.speed - 1) * 100)
    rate = f"{percentage:+d}%"

    # Create temporary MP3 file
    temp_file = tempfile.NamedTemporaryFile(
        suffix=".mp3",
        delete=False
    )
    temp_path = temp_file.name
    temp_file.close()

    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice=request.voice,
            rate=rate
        )

        await communicate.save(temp_path)

        if os.path.getsize(temp_path) == 0:
            raise Exception("Generated audio is empty")

        return FileResponse(
            path=temp_path,
            media_type="audio/mpeg",
            filename="chinese_audio.mp3",
            background=BackgroundTask(
                os.unlink,
                temp_path
            )
        )

    except Exception as error:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

        raise HTTPException(
            status_code=500,
            detail=f"TTS generation failed: {str(error)}"
        )
