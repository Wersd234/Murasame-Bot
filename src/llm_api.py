import json
import re
from openai import AsyncOpenAI
from config import LLM_BASE_URL, LLM_API_KEY, MODEL_NAME, logger

llm_client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


async def generate_reply(messages: list) -> dict:
    try:
        response = await llm_client.chat.completions.create(
            # 🌟 修改 1: max_tokens 从 500 改为 2048 (给模型留足思考和输出 JSON 的空间)
            model=MODEL_NAME, messages=messages, temperature=0.7, max_tokens=2048
        )
        if not getattr(response, 'choices', None) or len(response.choices) == 0:
            return None

        raw_content = response.choices[0].message.content
        if not raw_content: return None

        # 你的这行正则非常棒！能完美跳过前面的思考过程，提取 JSON
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


async def summarize_memory(current_memory: str, history: list, lang: str) -> str:
    """让大模型在后台总结对话，提炼出关键事实"""
    if lang == "zh":
        # 🌟 优化提示词：强烈要求模型不要输出思考过程，直接输出总结
        prompt = "请提取以下对话中关于用户的关键事实（例如：主人养了一只猫、主人明天要上班等）。请将新事实与[现有记忆]合并，写成一段简短的客观总结陈述。不要加入任何废话、主观感受、思考过程（thought）或对话格式，只输出事实本身。"
    else:
        prompt = "Extract key facts about the user from the following conversation. Combine new facts with [Existing Memory] into a single, concise paragraph of objective facts. Do not output any thought process or extra text."

    chat_text = ""
    for msg in history:
        content = msg['content']
        if isinstance(content, list): content = "[发送了一张图片]"
        chat_text += f"{msg['role']}: {content}\n"

    sys_content = f"{prompt}\n\n[Existing Memory]: {current_memory}\n\n[Conversation History]:\n{chat_text}"

    try:
        response = await llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": sys_content}],
            temperature=0.3,  
            # 🌟 修改 2: max_tokens 从 200 改为 1024 (同样防止提炼记忆时被截断)
            max_tokens=1024
        )
        if getattr(response, 'choices', None) and len(response.choices) > 0:
            raw_summary = response.choices[0].message.content.strip()
            
            # 🌟 新增安全机制：防止记忆被思考过程污染
            # 如果模型依然不听话输出了 <|channel>thought，我们要把它从记忆中剔除
            if "<|channel>thought" in raw_summary:
                # 尝试用正则剔除思考部分（这取决于你模型的具体输出格式）
                # 通常我们可以简单地截取最后一个换行符之后的内容，或者直接去掉标签内容
                clean_summary = re.sub(r'<\|channel>thought.*?(?=\n\n|\Z)', '', raw_summary, flags=re.DOTALL).strip()
                if clean_summary:
                    return clean_summary
            
            return raw_summary
            
    except Exception as e:
        logger.error(f"记忆提炼失败: {e}")

    return current_memory
