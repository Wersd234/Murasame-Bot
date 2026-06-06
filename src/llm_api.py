import json
import re
from openai import AsyncOpenAI
from config import LLM_BASE_URL, LLM_API_KEY, MODEL_NAME, logger

llm_client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


async def generate_reply(messages: list) -> dict:
    try:
        response = await llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        raw_reply = response.choices[0].message.content.strip()

        json_match = re.search(r'\{.*?\}', raw_reply, re.DOTALL)
        if json_match:
            clean_reply = json_match.group(0)
            try:
                return json.loads(clean_reply)
            except json.JSONDecodeError:
                logger.warning("Failed to decode JSON block.")
                return {"emotion": "other", "view": "front", "reply": raw_reply}
        else:
            logger.warning("No JSON block found in output.")
            return {"emotion": "other", "view": "front", "reply": raw_reply}

    except Exception as e:
        logger.error(f"LLM API Error: {e}", exc_info=True)
        return None