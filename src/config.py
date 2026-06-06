import os
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger('murasame_bot')

# ----------------- 路径定义 (适配新构型) -----------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

# 资源路径
MURASAME_BASE_PATH = os.path.join(PROJECT_ROOT, "resource", "murasame")
# 属性配置文件路径
PROPERTIES_DIR = os.path.join(PROJECT_ROOT, "properties")
PROMPTS_DIR = os.path.join(PROPERTIES_DIR, "system_prompts")
SETTINGS_FILE = os.path.join(PROPERTIES_DIR, "server_settings.json")

# ----------------- 配置加载 -----------------
OUTFIT_FOLDERS = {
    "kimono": "kimono",
    "maid": "maid",
    "sleepwear": "sleepwear",
    "uniform": "uniform"
}

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
MODEL_NAME = "gemma"

# 🌟 核心：一次性加载所有的 System Prompts
SYSTEM_PROMPTS = {}
# 加载英文
try:
    with open(os.path.join(PROMPTS_DIR, "system_prompt_EN.txt"), "r", encoding="utf-8") as f:
        SYSTEM_PROMPTS["en"] = f.read()
except FileNotFoundError:
    logger.error("❌ system_prompt_EN.txt not found!")
    SYSTEM_PROMPTS["en"] = "You are Murasame. Respond in JSON."
# 加载中文
try:
    with open(os.path.join(PROMPTS_DIR, "system_prompt_ZH.txt"), "r", encoding="utf-8") as f:
        SYSTEM_PROMPTS["zh"] = f.read()
except FileNotFoundError:
    logger.error("❌ system_prompt_ZH.txt not found!")
    SYSTEM_PROMPTS["zh"] = "你是丛雨。请用JSON回复。"


# ----------------- 动作触发配置 -----------------
ACTIONS_CONFIG = {
    "pat": {
        "triggers": ["pat", "摸摸", "摸头", "摸一下"],
        "emotion": "happy", "view": "front",
        "reply_en": "H-hey! Don't just pat me whenever you want... but I guess it's not the worst thing...",
        "reply_zh": "喂、喂！不要随便摸吾的头啊……不过，倒也不是很讨厌就是了……"
    },
    "headpat": {
        "triggers": ["headpat", "揉揉"],
        "emotion": "happy", "view": "front",
        "reply_en": "Stop it! My hair is going to get messy, Master!",
        "reply_zh": "快停下！头发要被主人弄乱了啦！"
    },
    "feed": {
        "triggers": ["feed", "喂食", "吃团子", "吃糖"],
        "emotion": "happy", "view": "front",
        "reply_en": "Is that a sweet? Finally, you're doing something right, Master.",
        "reply_zh": "那是甜点吗？总算做了件像样的事嘛，主人。"
    },
    "hug": {
        "triggers": ["hug", "抱抱", "抱一下"],
        "emotion": "surprised", "view": "front",
        "reply_en": "H-hug?! A-are you serious? Too close, Master, too close!",
        "reply_zh": "抱、抱抱？！汝认真的吗？太近了啦，主人，太近了！"
    },
    "tease": {
        "triggers": ["tease", "欺负", "笨蛋"],
        "emotion": "angry", "view": "side",
        "reply_en": "Are you picking a fight with me, Master? You're being very insolent today!",
        "reply_zh": "主人是想打架吗？今天怎么这么嚣张！"
    }
}

EMOTION_EMOJIS = {"happy": "✨", "angry": "💢", "sad": "💧", "surprised": "❗"}