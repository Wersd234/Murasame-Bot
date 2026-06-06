import os
import sys
import json
import random
from config import MURASAME_BASE_PATH, OUTFIT_FOLDERS, DISCORD_TOKEN, SETTINGS_FILE, PROMPTS_DIR, logger


def load_server_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_server_language(guild_id: str, lang: str):
    settings = load_server_settings()
    settings[str(guild_id)] = lang
    # 如果 properties 目录不存在则创建
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)


def get_server_language(guild_id: str) -> str:
    settings = load_server_settings()
    return settings.get(str(guild_id), "en")


def run_startup_check():
    """开机自检逻辑"""
    logger.info("🔍 [自检] 开始执行系统开机自检...")
    passed = True

    if not DISCORD_TOKEN or DISCORD_TOKEN == "your_token_here":
        logger.error("❌ [自检失败] .env 文件中缺少 DISCORD_BOT_TOKEN！")
        passed = False
    else:
        logger.info("✅ [自检通过] 成功读取 Discord Token")

    # 检查两个 Prompt 文件
    for lang in ["EN", "ZH"]:
        prompt_path = os.path.join(PROMPTS_DIR, f"system_prompt_{lang}.txt")
        if not os.path.exists(prompt_path):
            logger.warning(f"⚠️ [自检警告] 找不到提示词文件: {prompt_path}")
        else:
            logger.info(f"✅ [自检通过] 成功读取 system_prompt_{lang}.txt")

    if not os.path.exists(MURASAME_BASE_PATH):
        logger.error(f"❌ [自检失败] 找不到资源基础目录: {MURASAME_BASE_PATH}")
        passed = False
    else:
        logger.info("✅ [自检通过] 找到资源基础目录")

    if not passed:
        logger.critical("🛑 [开机中止] 严重文件缺失，请修复后再启动 Bot！")
        sys.exit(1)
    else:
        logger.info("🎉 [自检完成] 所有核心组件就绪，准备连接 Discord...")


def get_random_emotion_image(outfit: str, emotion: str, view: str):
    emotion, view = emotion.lower().strip(), view.lower().strip()
    outfit = outfit.lower().strip()

    if view not in ["front", "side"]: view = "front"
    if emotion in ["neutral", "normal", "none", ""]: emotion = random.choice(["happy", "other"])

    folder_name = OUTFIT_FOLDERS.get(outfit, "kimono")
    outfit_path = os.path.join(MURASAME_BASE_PATH, folder_name)
    if not os.path.exists(outfit_path):
        outfit_path = os.path.join(MURASAME_BASE_PATH, OUTFIT_FOLDERS["kimono"])

    folder_path = os.path.join(outfit_path, view, emotion)
    valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.gif')

    def get_img_from(path):
        if os.path.exists(path):
            imgs = [f for f in os.listdir(path) if
                    f.lower().endswith(valid_exts) and os.path.isfile(os.path.join(path, f))]
            if imgs: return os.path.join(path, random.choice(imgs))
        return None

    img = get_img_from(folder_path)
    if img: return img
    img = get_img_from(os.path.join(outfit_path, view, "other"))
    if img: return img
    img = get_img_from(os.path.join(outfit_path, "front", "other"))
    if img: return img
    img = get_img_from(outfit_path)
    if img: return img

    fallback_kimono = os.path.join(MURASAME_BASE_PATH, OUTFIT_FOLDERS["kimono"], "front", "other")
    img = get_img_from(fallback_kimono)
    if img: return img

    return None