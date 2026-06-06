import json
import re
from openai import AsyncOpenAI
from config import LLM_BASE_URL, LLM_API_KEY, MODEL_NAME, logger

llm_client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


async def generate_reply(messages: list) -> dict:
    try:
        response = await llm_client.chat.completions.create(
            model=MODEL_NAME, messages=messages, temperature=0.7, max_tokens=500
        )
        if not getattr(response, 'choices', None) or len(response.choices) == 0:
            return None

        raw_content = response.choices[0].message.content
        if not raw_content: return None

        json_match = re.search(r'\{.*?\}', raw_content.strip(), re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return {"emotion": "other", "view": "front", "reply": raw_content.strip()}
    except Exception as e:
        logger.error(f"LLM API Error: {e}")
        return None


# 🌟 新增：记忆提炼函数 (刚才缺失的就是这个！)
async def summarize_memory(current_memory: str, history: list, lang: str) -> str:
    """让大模型在后台总结对话，提炼出关键事实"""
    if lang == "zh":
        prompt = "请提取以下对话中关于用户的关键事实（例如：主人养了一只猫、主人明天要上班等）。请将新事实与[现有记忆]合并，写成一段简短的客观总结陈述。不要加入任何废话、主观感受或对话格式，只输出事实本身。"
    else:
        prompt = "Extract key facts about the user from the following conversation. Combine new facts with [Existing Memory] into a single, concise paragraph of objective facts. Do not output anything else."

    # 将图片等多模态内容转为纯文本格式进行总结，防止报错
    chat_text = ""
    for msg in history:
        content = msg['content']
        if isinstance(content, list): content = "[发送了一张图片]"
        chat_text += f"{msg['role']}: {content}\n"

    sys_content = f"{prompt}\n\n[Existing Memory]: {current_memory}\n\n[Conversation History]:\n{chat_text}"

    try:
        # 调用大模型生成记忆总结
        response = await llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": sys_content}],
            temperature=0.3,  # 降低温度，确保总结的是客观事实而不去瞎编
            max_tokens=200
        )
        if getattr(response, 'choices', None) and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"记忆提炼失败: {e}")

    return current_memory