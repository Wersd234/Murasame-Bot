import os
import sys
import json
import random
import io
import discord
# 🌟 新增：引入 ImageFilter(滤镜) 和 ImageEnhance(图像增强)
from PIL import Image, ImageFilter, ImageEnhance
from config import MURASAME_BASE_PATH, OUTFIT_FOLDERS, DISCORD_TOKEN, SETTINGS_FILE, MEMORY_FILE, PROMPTS_DIR, \
    BACKGROUNDS_DIR, PHASE_BACKGROUND_MAPPING, logger


# ----------------- 配置文件读写 -----------------
def load_server_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return {}


def save_server_language(guild_id: str, lang: str):
    settings = load_server_settings()
    settings[str(guild_id)] = lang
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f: json.dump(settings, f, indent=4)


def get_server_language(guild_id: str) -> str:
    return load_server_settings().get(str(guild_id), "en")


def save_bg_setting(guild_id: str, enabled: bool):
    settings = load_server_settings()
    settings[f"{guild_id}_bg"] = enabled
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f: json.dump(settings, f, indent=4)


def get_bg_setting(guild_id: str) -> bool:
    return load_server_settings().get(f"{guild_id}_bg", True)


# ----------------- 长期记忆读写 -----------------
def load_long_term_memory(channel_id: str) -> str:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get(str(channel_id), "")
    return ""


def save_long_term_memory(channel_id: str, summary: str):
    mem = {}
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f: mem = json.load(f)
    mem[str(channel_id)] = summary
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f: json.dump(mem, f, indent=4, ensure_ascii=False)


# ----------------- 图像与自检逻辑 -----------------
def run_startup_check():
    logger.info("🔍 [自检] 开始执行系统开机自检...")
    passed = True
    if not DISCORD_TOKEN or DISCORD_TOKEN == "your_token_here":
        logger.error("❌ 缺少 DISCORD_BOT_TOKEN");
        passed = False
    if not os.path.exists(MURASAME_BASE_PATH):
        logger.error("❌ 找不到立绘目录");
        passed = False
    if not os.path.exists(BACKGROUNDS_DIR):
        logger.warning("⚠️ 找不到背景目录，将回退为发送透明立绘。")

    if not passed:
        logger.critical("🛑 严重文件缺失，中止启动！")
        sys.exit(1)
    logger.info("🎉 [自检完成] 准备连接 Discord...")


def get_character_image_path(outfit: str, emotion: str, view: str):
    emotion, view = emotion.lower().strip(), view.lower().strip()
    outfit = outfit.lower().strip()
    if view not in ["front", "side"]: view = "front"
    if emotion in ["neutral", "normal", "none", ""]: emotion = random.choice(["happy", "other"])

    folder_name = OUTFIT_FOLDERS.get(outfit, "kimono")
    outfit_path = os.path.join(MURASAME_BASE_PATH, folder_name)
    if not os.path.exists(outfit_path): outfit_path = os.path.join(MURASAME_BASE_PATH, OUTFIT_FOLDERS["kimono"])

    valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.gif')

    def get_img_from(path):
        if os.path.exists(path):
            imgs = [f for f in os.listdir(path) if
                    f.lower().endswith(valid_exts) and os.path.isfile(os.path.join(path, f))]
            if imgs: return os.path.join(path, random.choice(imgs))
        return None

    for p in [os.path.join(outfit_path, view, emotion), os.path.join(outfit_path, view, "other"),
              os.path.join(outfit_path, "front", "other"), outfit_path]:
        img = get_img_from(p)
        if img: return img
    return get_img_from(os.path.join(MURASAME_BASE_PATH, OUTFIT_FOLDERS["kimono"], "front", "other"))


def get_random_emotion_image(outfit: str, emotion: str, view: str):
    return get_character_image_path(outfit, emotion, view)


def generate_scene_image(outfit: str, emotion: str, view: str, phase: str) -> discord.File:
    char_path = get_character_image_path(outfit, emotion, view)
    if not char_path: return None

    if not os.path.exists(BACKGROUNDS_DIR): return discord.File(char_path)

    bg_info = PHASE_BACKGROUND_MAPPING.get(phase, {"prefix": "神社_境内", "suffix": "A"})
    bg_candidates = [f for f in os.listdir(BACKGROUNDS_DIR) if
                     f.startswith(bg_info["prefix"]) and f.endswith(f'{bg_info["suffix"]}.png')]
    if not bg_candidates:
        bg_candidates = [f for f in os.listdir(BACKGROUNDS_DIR) if f.startswith(bg_info["prefix"])]
    if not bg_candidates:
        return discord.File(char_path)

    bg_path = os.path.join(BACKGROUNDS_DIR, random.choice(bg_candidates))

    try:
        bg = Image.open(bg_path).convert("RGBA")
        char = Image.open(char_path).convert("RGBA")

        # 1. 裁切各自的透明白边
        alpha_bbox_bg = bg.split()[-1].getbbox()
        if alpha_bbox_bg: bg = bg.crop(alpha_bbox_bg)

        char_bbox = char.split()[-1].getbbox()
        if char_bbox: char = char.crop(char_bbox)

        # 🌟 核心构图魔法：全局放大系数 (当前设为 1.1 倍)
        scale_factor = 1.1

        # 设定最终画面的固定高度为 900 像素的基础值 * 放大系数
        canvas_h = int(900 * scale_factor)

        # 缩放立绘：让全身占据画面高度的 95% (头顶和脚底留出呼吸感)
        char_target_h = int(canvas_h * 0.95)
        char_scale = char_target_h / char.height
        char_target_w = int(char.width * char_scale)
        char = char.resize((char_target_w, char_target_h), Image.Resampling.LANCZOS)

        # 设定画面宽度：最低宽度 600 也同步乘以放大系数
        canvas_w = max(int(600 * scale_factor), int(char_target_w * 1.6))

        # 🌟 背景适配魔法：放大背景，并裁掉左右两边多余的部分
        # 计算背景缩放比例 (保证背景能完全铺满这块竖向的画布)
        bg_scale = max(canvas_w / bg.width, canvas_h / bg.height)
        bg_scaled_w = int(bg.width * bg_scale)
        bg_scaled_h = int(bg.height * bg_scale)
        bg = bg.resize((bg_scaled_w, bg_scaled_h), Image.Resampling.LANCZOS)

        # 从正中间裁切出我们需要的那一块背景
        left = (bg.width - canvas_w) // 2
        top = (bg.height - canvas_h) // 2
        right = left + canvas_w
        bottom = top + canvas_h
        bg = bg.crop((left, top, right, bottom))

        # 景深与调色 (保留)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=2))
        enhancer = ImageEnhance.Brightness(bg)
        bg = enhancer.enhance(0.85)

        # 合成画布
        canvas = Image.new("RGBA", (canvas_w, canvas_h))
        canvas.paste(bg, (0, 0))

        # 人物居中对齐，底部留出 2% 的地面空间不切脚
        x = (canvas_w - char.width) // 2
        y = canvas_h - char.height - int(canvas_h * 0.02)
        canvas.paste(char, (x, y), char)

        final_image = canvas.convert("RGB")
        img_byte_arr = io.BytesIO()
        final_image.save(img_byte_arr, format='JPEG', quality=85)
        img_byte_arr.seek(0)
        return discord.File(fp=img_byte_arr, filename="scene.jpg")
    except Exception as e:
        logger.error(f"合成背景失败: {e}")
        return discord.File(char_path)