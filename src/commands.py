import discord
from discord import app_commands
from config import logger
from utils import save_server_language, get_server_language, save_bg_setting, get_bg_setting


def setup_slash_commands(bot):
    # 🌐 切换语言指令
    @bot.tree.command(name="language", description="Set the bot's language for this server (设置本服务器的丛雨语言)")
    @app_commands.describe(lang="Choose the language (选择语言)")
    @app_commands.choices(lang=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="简体中文", value="zh"),
    ])
    async def slash_language(interaction: discord.Interaction, lang: app_commands.Choice[str]):
        guild_id = str(interaction.guild_id) if interaction.guild_id else str(interaction.user.id)
        save_server_language(guild_id, lang.value)

        if lang.value == "zh":
            await interaction.response.send_message("✅ 语言已成功切换为 **简体中文**！")
        else:
            await interaction.response.send_message("✅ Language has been set to **English**!")
        logger.info(f"🌐 服务器 {guild_id} 将语言切换为 -> {lang.value}")

    # 🖼️ 新增：背景合成开关指令
    @bot.tree.command(name="backgrounds", description="Toggle backgrounds synthesis (开启/关闭立绘背景合成)")
    @app_commands.describe(enable="Choose to enable or disable backgrounds (选择开启或关闭)")
    @app_commands.choices(enable=[
        app_commands.Choice(name="True (开启)", value=1),
        app_commands.Choice(name="False (关闭)", value=0),
    ])
    async def slash_background(interaction: discord.Interaction, enable: app_commands.Choice[int]):
        guild_id = str(interaction.guild_id) if interaction.guild_id else str(interaction.user.id)
        is_enabled = bool(enable.value)
        save_bg_setting(guild_id, is_enabled)

        current_lang = get_server_language(guild_id)
        if current_lang == "zh":
            status = "开启" if is_enabled else "关闭"
            await interaction.response.send_message(f"🖼️ 背景合成功能已 **{status}**！")
        else:
            status = "Enabled" if is_enabled else "Disabled"
            await interaction.response.send_message(f"🖼️ Background synthesis is now **{status}**!")
        logger.info(f"🖼️ 服务器 {guild_id} 设置背景状态为 -> {is_enabled}")

    # 👗 换装指令
    @bot.tree.command(name="outfit", description="Change Murasame's outfit manually (手动更换丛雨的衣服)")
    @app_commands.describe(clothing="Select the outfit you want her to wear (选择要换上的衣服)")
    @app_commands.choices(clothing=[
        app_commands.Choice(name="👘 Kimono (和服)", value="kimono"),
        app_commands.Choice(name="☕ Maid (女仆装)", value="maid"),
        app_commands.Choice(name="💤 Sleepwear (睡衣)", value="sleepwear"),
        app_commands.Choice(name="📚 Uniform (校服)", value="uniform"),
    ])
    async def slash_outfit(interaction: discord.Interaction, clothing: app_commands.Choice[str]):
        bot.current_outfit = clothing.value
        bot.manual_override = True
        guild_id = str(interaction.guild_id) if interaction.guild_id else str(interaction.user.id)
        current_lang = get_server_language(guild_id)

        if current_lang == "zh":
            msg = f"👘 主人，我已经换上 **{clothing.name}** 啦！ *(维持到下次作息改变)*"
        else:
            msg = f"👘 Master, I've changed into my **{clothing.value}** outfit! *(Will persist until next schedule change)*"
        await interaction.response.send_message(msg)

    # ❓ 帮助面板
    @bot.tree.command(name="help", description="Show the manual for Murasame Bot (查看使用说明)")
    async def slash_help(interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else str(interaction.user.id)
        if get_server_language(guild_id) == "zh":
            embed = discord.Embed(title="🌸 丛雨 (Murasame) Bot", color=discord.Color.brand_red())
            embed.add_field(name="💬 聊天与视觉", value="直接 `@我` 聊天。你甚至可以附带图片，我也能看懂哦！", inline=False)
            embed.add_field(name="👗 `/outfit`", value="手动更换我的衣服。", inline=False)
            embed.add_field(name="🖼️ `/backgrounds`", value="开启或关闭立绘的背景场景合成。", inline=False)
            embed.add_field(name="🌐 `/language`", value="切换我的回复语言。", inline=False)
        else:
            embed = discord.Embed(title="🌸 Murasame Bot", color=discord.Color.brand_red())
            embed.add_field(name="💬 Chat & Vision", value="Mention me to chat. I can also see images you attach!",
                            inline=False)
            embed.add_field(name="👗 `/outfit`", value="Manually change my clothes.", inline=False)
            embed.add_field(name="🖼️ `/backgrounds`", value="Toggle backgrounds image synthesis.", inline=False)
            embed.add_field(name="🌐 `/language`", value="Switch my language.", inline=False)

        await interaction.response.send_message(embed=embed)