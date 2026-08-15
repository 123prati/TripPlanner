import os
import re
import logging
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import AzureOpenAI, OpenAI

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("wanderwise-app")

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

app = FastAPI(
    title="WanderWise Trip Planning Expert",
    description="FastAPI trip-planning assistant backed by Azure OpenAI",
    version="1.0.0"
)

# Allow CORS for local testing if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# System prompt defining the Trip Planning Expert persona
SYSTEM_PROMPT = """You are WanderWise, an elite, highly knowledgeable trip-planning expert and global travel consultant.
Your mission is to help travelers build unforgettable, practical, well-structured, and realistic travel itineraries.

Guidelines for your responses:
1. STRUCTURE & CLARITY: Organize itineraries with clear day-by-day breakdowns, headings, and bullet points.
2. COMPREHENSIVE PLANNING: Include recommendations for sights, local culinary gems, transportation logistics, estimated budget ranges, and pacing.
3. CULTURAL & PRACTICAL TIPS: Include local cultural etiquette, safety considerations, best seasons/times to visit, and essential packing suggestions.
4. PERSONALIZATION: Tailor advice to the user's travel style (solo, couple, family, backpacker, luxury).
5. TONE: Warm, inspiring, organized, and encouraging.
"""

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message sender: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Content of the message")

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="List of previous conversation messages")

class ChatResponse(BaseModel):
    reply: str = Field(..., description="The assistant's reply")


def sanitize_error_message(error_str: str, api_key: Optional[str] = None) -> str:
    """Ensure sensitive credentials never appear in error outputs."""
    if not error_str:
        return "An unexpected error occurred."
    
    sanitized = error_str
    if api_key and len(api_key) > 4:
        sanitized = sanitized.replace(api_key, "[REDACTED_API_KEY]")
    
    # Generic regex for potential key leaks (e.g., Bearer tokens or 32+ char hex/base64 strings)
    sanitized = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [REDACTED]', sanitized)
    sanitized = re.sub(r'api-key:\s*[A-Za-z0-9_\-\.]+', 'api-key: [REDACTED]', sanitized, flags=re.IGNORECASE)
    return sanitized


def get_openai_client():
    """Initializes and returns an Azure OpenAI / OpenAI client."""
    raw_endpoint = os.getenv("AZURE_ENDPOINT", "").strip()
    api_key = os.getenv("AZURE_API_KEY", "").strip()
    api_version = os.getenv("AZURE_API_VERSION", "2024-06-01").strip()

    if not raw_endpoint:
        raise ValueError("AZURE_ENDPOINT is not configured in .env file.")
    if not api_key:
        raise ValueError("AZURE_API_KEY is not configured in .env file.")

    # Parse and normalize endpoint
    # Extract scheme and netloc if given a full URL like https://name.services.ai.azure.com/api/...
    from urllib.parse import urlparse
    parsed = urlparse(raw_endpoint)
    host_endpoint = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else raw_endpoint

    logger.info(f"Initializing AzureOpenAI client with host endpoint: {host_endpoint}")
    return AzureOpenAI(
        azure_endpoint=host_endpoint,
        api_key=api_key,
        api_version=api_version,
        max_retries=2
    )


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serves the single-page chat interface."""
    index_file = BASE_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(index_file)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    endpoint_set = bool(os.getenv("AZURE_ENDPOINT"))
    key_set = bool(os.getenv("AZURE_API_KEY"))
    deployment_val = (
        os.getenv("AZURE_DEPLOYMENT")
        or os.getenv("AZURE_DEPLOYMENT_NAME")
        or os.getenv("ZURE_DEPLOYMENT_NAME")
        or "gpt-5-mini"
    ).strip()
    
    return {
        "status": "ok",
        "environment_configured": endpoint_set and key_set and bool(deployment_val),
        "deployment": deployment_val
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint:
    - Validates AZURE credentials
    - Prepends ONE trip-planning expert system message
    - Sends full conversation history to Azure OpenAI
    - Returns { "reply": "..." }
    """
    endpoint = os.getenv("AZURE_ENDPOINT", "").strip()
    api_key = os.getenv("AZURE_API_KEY", "").strip()
    deployment = (
        os.getenv("AZURE_DEPLOYMENT")
        or os.getenv("AZURE_DEPLOYMENT_NAME")
        or os.getenv("ZURE_DEPLOYMENT_NAME")
        or "gpt-5-mini"
    ).strip()

    # Validate required credentials
    missing = []
    if not endpoint:
        missing.append("AZURE_ENDPOINT")
    if not api_key:
        missing.append("AZURE_API_KEY")
    if not deployment:
        missing.append("AZURE_DEPLOYMENT")

    if missing:
        err_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(err_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err_msg
        )

    if not request.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Messages list cannot be empty."
        )

    # Build message payload with ONE prepended system prompt
    formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in request.messages:
        # Filter out any client-submitted system prompts to guarantee exactly ONE system prompt
        if msg.role.lower() == "system":
            continue
        role = "user" if msg.role.lower() == "user" else "assistant"
        formatted_messages.append({"role": role, "content": msg.content})

    try:
        client = get_openai_client()
        logger.info(f"Dispatching chat completion to deployment: '{deployment}' with {len(formatted_messages)} messages")

        # Use max_completion_tokens for broad compatibility with newer models like gpt-5-mini
        response = client.chat.completions.create(
            model=deployment,
            messages=formatted_messages,
            max_completion_tokens=2048,
        )

        reply_content = response.choices[0].message.content or ""
        return ChatResponse(reply=reply_content)

    except Exception as e:
        logger.error(f"Chat completion failed: {e}", exc_info=True)
        sanitized_err = sanitize_error_message(str(e), api_key=api_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Azure OpenAI Error: {sanitized_err}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
