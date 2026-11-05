import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from openai import AsyncOpenAI, OpenAIError

app = FastAPI(title="BLACK-K92N-WOLF OpenAI Lab", version="0.1.0")

class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)

class PromptResponse(BaseModel):
    text: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/v1/respond", response_model=PromptResponse)
async def respond(body: PromptRequest):
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    client = AsyncOpenAI(api_key=key, timeout=20.0, max_retries=0)
    try:
        result = await client.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), input=body.prompt)
        return PromptResponse(text=result.output_text)
    except OpenAIError:
        raise HTTPException(status_code=502, detail="Upstream AI service failed")
