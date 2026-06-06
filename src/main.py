import discord
from discord import app_commands
from discord.ext import tasks
import re
import datetime
import base64
import io
from PIL import Image
from collections import deque

from config import DISCORD_TOKEN, SYSTEM_PROMPTS, ACTIONS_CONFIG, EMOTION_EMOJIS, logger
from utils import get_random_emotion_image, run_startup_check, get_server_language
from llm_api import generate_reply
from commands import setup_slash_commands


class AnimeBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.history = {}
        self.current_outfit = "kimono"
        self.current_time_phase = None
        self.manual_override = False

    async def setup_hook(self):
        self.dynamic_presence.start()
        await self.tree.sync()
        logger.info("✅ Slash commands 同步完成！")

    async def on_ready(self):
        logger.info(f"✅ Bot '{self.user.name}' is Online | Multimodal Vision Enabled.")

    @tasks.loop(minutes=10)
    async def dynamic_presence(self):
        now = datetime.datetime.now()
        hour = now.hour
        is_weekend = now.weekday() >= 5

        if hour >= 22 or hour < 7:
            phase = "night_sleep"
            auto_outfit = "sleepwear"
            status = "💤 Sleeping | 呼呼大睡中"
        elif is_weekend:
            phase = "weekend_day"
            auto_outfit = "kimono"
            status = "🌞 Weekend | 享受周末时光"
        else:
            if 7 <= hour < 9:
                phase = "weekday_morning"
                auto_outfit = "kimono"
                status = "🧹 Sweeping | 正在打扫神社"
            elif 9 <= hour < 16:
                phase = "weekday_school"
                auto_outfit = "uniform"
                status = "📚 School | 在学校上课"
            elif 16 <= hour < 20:
                phase = "weekday_job"
                auto_outfit = "maid"
                status = "☕ Maid Job | 女仆咖啡厅打工"
            else:
                phase = "weekday_evening"
                auto_outfit = "kimono"
                status = "🏮 Relaxing | 在神社休息"

        if self.current_time_phase != phase:
            self.current_time_phase = phase
            self.manual_override = False
            self.current_outfit = auto_outfit

        display_status = status
        if self.manual_override:
            display_status += f" (Wearing {self.current_outfit})"

        await self.change_presence(activity=discord.Game(name=display_status))

    @dynamic_presence.before_loop
    async def before_dynamic_presence(self):
        await self.wait_until_ready()

    async def on_message(self, message):
        if message.author == self.user:
            return

        content = message.content.lower().strip()
        is_mentioned = self.user in message.mentions
        is_reply = message.reference and getattr(message.reference.resolved, 'author', None) == self.user

        if not (is_mentioned or is_reply):
            return

        guild_id = str(message.guild.id) if message.guild else str(message.author.id)
        current_lang = get_server_language(guild_id)

        # ----------------- 动作触发器 -----------------
        for action, data in ACTIONS_CONFIG.items():
            triggered = False
            for trigger in data["triggers"]:
                if re.search(r'[a-zA-Z]', trigger):
                    if re.search(rf'\b{trigger}\b', content, re.IGNORECASE):
                        triggered = True;
                        break
                else:
                    if trigger in content:
                        triggered = True;
                        break

            if triggered:
                async with message.channel.typing():
                    img = get_random_emotion_image(self.current_outfit, data["emotion"], data["view"])
                    reply_text = data.get(f"reply_{current_lang}", data["reply_en"])

                    if img:
                        await message.reply(content=reply_text, file=discord.File(img))
                    else:
                        await message.reply(content=reply_text)
                return

        # ----------------- 多模态与对话逻辑 -----------------
        # ⚠️ 修复点：这里如果缺少就会报 KeyError！
        if message.channel.id not in self.history:
            self.history[message.channel.id] = deque(maxlen=10)

        async with message.channel.typing():
            user_input_text = message.content.replace(f'<@{self.user.id}>', '').strip()

            image_bytes = None
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    image_bytes = await attachment.read()
                    logger.info("📸 检测到图片附件，正在进行压缩与标准化转码...")
                    break

            if image_bytes:
                try:
                    # 压缩图片并转换为标准 JPEG Base64
                    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                    img.thumbnail((1024, 1024))  # 等比例压缩限制大小

                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=85)
                    base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

                    user_msg_content = []
                    text_prompt = user_input_text if user_input_text else (
                        "看看这张图片。" if current_lang == "zh" else "Look at this image.")
                    user_msg_content.append({"type": "text", "text": text_prompt})
                    user_msg_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    })
                    logger.info("✅ 图片转码完成，已送入大模型！")
                except Exception as e:
                    logger.error(f"处理图片失败: {e}")
                    user_msg_content = user_input_text or "..."
            else:
                user_msg_content = user_input_text or "..."

            # 组装 System Prompt
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            base_prompt = SYSTEM_PROMPTS.get(current_lang, SYSTEM_PROMPTS["en"])
            time_aware_prompt = base_prompt + (
                f"\n\n[System Note: The current local time is {current_time}. "
                f"You are currently wearing a '{self.current_outfit}' outfit.]"
            )

            messages = [{"role": "system", "content": time_aware_prompt}]

            # 填入历史记忆
            for entry in self.history[message.channel.id]:
                messages.append(entry)

            messages.append({"role": "user", "content": user_msg_content})

            # 调用大模型
            llm_response = await generate_reply(messages)

            if llm_response is None:
                error_msg = "*(似乎出了点小问题，丛雨现在无法回答...)*" if current_lang == "zh" else "*(Something went wrong while Murasame was trying to reply...)*"
                await message.reply(error_msg)
                return

            emotion = llm_response.get("emotion", "other")
            view = llm_response.get("view", "front")
            reply_text = llm_response.get("reply", "...")

            # 记忆储存：图文只存文本部分，防崩溃
            self.history[message.channel.id].append(
                {"role": "user", "content": user_input_text if user_input_text else "[发送了一张图片]"})
            self.history[message.channel.id].append({"role": "assistant", "content": reply_text})

            image_path = get_random_emotion_image(self.current_outfit, emotion, view)
            if image_path:
                await message.reply(content=reply_text, file=discord.File(image_path))
            else:
                await message.reply(content=reply_text)

            target_emoji = EMOTION_EMOJIS.get(emotion.lower(), "🍡")
            await message.add_reaction(target_emoji)


if __name__ == "__main__":
    run_startup_check()
    intents = discord.Intents.default()
    intents.message_content = True
    bot = AnimeBot(intents=intents)
    setup_slash_commands(bot)
    bot.run(DISCORD_TOKEN)