import discord
from discord import app_commands
from discord.ext import tasks
import re
import datetime
import base64
import io
import asyncio
from PIL import Image
from collections import deque

from config import DISCORD_TOKEN, SYSTEM_PROMPTS, ACTIONS_CONFIG, EMOTION_EMOJIS, logger
from utils import generate_scene_image, get_random_emotion_image, run_startup_check, get_server_language, \
    load_long_term_memory, save_long_term_memory, get_bg_setting
from llm_api import generate_reply, summarize_memory
from commands import setup_slash_commands


class AnimeBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.history = {}
        self.msg_count = {}
        self.current_outfit = "kimono"
        self.current_time_phase = "weekday_evening"
        self.manual_override = False

    async def setup_hook(self):
        self.dynamic_presence.start()
        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"✅ Bot '{self.user.name}' is Online | Memory & Scene Enabled.")

    @tasks.loop(minutes=10)
    async def dynamic_presence(self):
        now = datetime.datetime.now()
        hour = now.hour
        is_weekend = now.weekday() >= 5

        # 1. 每天的固定睡觉时间 (22:00 到次日 07:00)
        if hour >= 22 or hour < 7:
            phase, auto_outfit, status = "night_sleep", "sleepwear", "💤 Sleeping | 呼呼大睡中"

        # 2. 如果不是睡觉时间，且今天是周末
        elif is_weekend:
            if 7 <= hour < 18:
                phase, auto_outfit, status = "weekend_day", "kimono", "🏠 Staying Home | 周末宅家休息"
            else:
                phase, auto_outfit, status = "weekend_evening", "kimono", "🏠 Relaxing at Home | 晚上在客厅看剧"

        # 3. 如果不是睡觉时间，且今天是工作日
        else:
            if 7 <= hour < 9:
                phase, auto_outfit, status = "weekday_morning", "kimono", "🧹 Sweeping | 正在打扫神社"
            elif 9 <= hour < 16:
                phase, auto_outfit, status = "weekday_school", "uniform", "📚 School | 在学校上课"
            elif 16 <= hour < 20:
                phase, auto_outfit, status = "weekday_job", "maid", "☕ Maid Job | 女仆咖啡厅打工"
            else:
                # 剩下的时间就是 20:00 到 22:00
                phase, auto_outfit, status = "weekday_evening", "kimono", "🏮 Relaxing | 在神社休息"

        if self.current_time_phase != phase:
            self.current_time_phase = phase
            self.manual_override = False
            self.current_outfit = auto_outfit

        display_status = status + (f" (Wearing {self.current_outfit})" if self.manual_override else "")
        await self.change_presence(activity=discord.Game(name=display_status))

    @dynamic_presence.before_loop
    async def before_dynamic_presence(self):
        await self.wait_until_ready()

    async def update_memory_task(self, channel_id: str, history_copy: list, lang: str):
        current_mem = load_long_term_memory(channel_id)
        new_mem = await summarize_memory(current_mem, history_copy, lang)
        if new_mem and new_mem != current_mem:
            save_long_term_memory(channel_id, new_mem)
            logger.info(f"🧠 [记忆进化] 新记忆已写入: {new_mem}")

    async def on_message(self, message):
        if message.author == self.user: return
        content = message.content.lower().strip()
        if not (self.user in message.mentions or (
                message.reference and getattr(message.reference.resolved, 'author', None) == self.user)):
            return

        guild_id = str(message.guild.id) if message.guild else str(message.author.id)
        channel_id = str(message.channel.id)
        current_lang = get_server_language(guild_id)
        bg_enabled = get_bg_setting(guild_id)  # 🌟 读取背景开关状态

        # ----------------- 动作触发器 -----------------
        for action, data in ACTIONS_CONFIG.items():
            triggered = any(
                (re.search(rf'\b{t}\b', content, re.IGNORECASE) if re.search(r'[a-zA-Z]', t) else t in content) for t in
                data["triggers"])
            if triggered:
                async with message.channel.typing():
                    # 🌟 根据开关决定发合成图还是透明底图
                    if bg_enabled:
                        img_file = await asyncio.to_thread(generate_scene_image, self.current_outfit, data["emotion"],
                                                           data["view"], self.current_time_phase)
                    else:
                        img_path = get_random_emotion_image(self.current_outfit, data["emotion"], data["view"])
                        img_file = discord.File(img_path) if img_path else None

                    reply_text = data.get(f"reply_{current_lang}", data["reply_en"])
                    if img_file:
                        await message.reply(content=reply_text, file=img_file)
                    else:
                        await message.reply(content=reply_text)
                return

        # ----------------- 多模态与对话逻辑 -----------------
        if channel_id not in self.history: self.history[channel_id] = deque(maxlen=10)

        async with message.channel.typing():
            user_input_text = message.content.replace(f'<@{self.user.id}>', '').strip()

            image_bytes = None
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    image_bytes = await attachment.read()
                    break

            if image_bytes:
                try:
                    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                    img.thumbnail((1024, 1024))
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=85)
                    base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    user_msg_content = [
                        {"type": "text", "text": user_input_text or (
                            "看看这张图片。" if current_lang == "zh" else "Look at this image.")},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                except Exception as e:
                    logger.error(f"处理图片失败: {e}")
                    user_msg_content = user_input_text or "..."
            else:
                user_msg_content = user_input_text or "..."

            long_term_mem = load_long_term_memory(channel_id)
            mem_prompt = f"\n\n[Core Memory regarding the User]: {long_term_mem}" if long_term_mem else ""
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            base_prompt = SYSTEM_PROMPTS.get(current_lang, SYSTEM_PROMPTS["en"])
            time_aware_prompt = base_prompt + (
                f"\n\n[System Note: The current local time is {current_time}. "
                f"You are currently wearing a '{self.current_outfit}' outfit.]"
            ) + mem_prompt

            messages = [{"role": "system", "content": time_aware_prompt}]
            for entry in self.history[channel_id]: messages.append(entry)
            messages.append({"role": "user", "content": user_msg_content})

            llm_response = await generate_reply(messages)
            if llm_response is None:
                await message.reply(
                    "*(似乎出了点小问题，丛雨现在无法回答...)*" if current_lang == "zh" else "*(Error...)*")
                return

            emotion, view, reply_text = llm_response.get("emotion", "other"), llm_response.get("view",
                                                                                               "front"), llm_response.get(
                "reply", "...")

            self.history[channel_id].append(
                {"role": "user", "content": user_input_text if user_input_text else "[发送了一张图片]"})
            self.history[channel_id].append({"role": "assistant", "content": reply_text})

            self.msg_count[channel_id] = self.msg_count.get(channel_id, 0) + 1
            if self.msg_count[channel_id] % 10 == 0:
                history_copy = list(self.history[channel_id])
                asyncio.create_task(self.update_memory_task(channel_id, history_copy, current_lang))

            # 🌟 发图前检查开关，决定用哪种方式出图
            if bg_enabled:
                img_file = await asyncio.to_thread(generate_scene_image, self.current_outfit, emotion, view,
                                                   self.current_time_phase)
            else:
                img_path = get_random_emotion_image(self.current_outfit, emotion, view)
                img_file = discord.File(img_path) if img_path else None

            if img_file:
                await message.reply(content=reply_text, file=img_file)
            else:
                await message.reply(content=reply_text)

            await message.add_reaction(EMOTION_EMOJIS.get(emotion.lower(), "🍡"))


if __name__ == "__main__":
    run_startup_check()
    intents = discord.Intents.default()
    intents.message_content = True
    bot = AnimeBot(intents=intents)
    setup_slash_commands(bot)
    bot.run(DISCORD_TOKEN)