import discord
from discord import app_commands
from config import logger
from utils import save_server_language, get_server_language


def setup_slash_commands(bot):
    # 🌐 切换语言指令
    @bot.tree.command(name="language", description="Set the bot's language for this server (设置本服务器的丛雨语言)")
    @app_commands.describe(lang="Choose the language (选择语言)")
    @app_commands.choices(lang=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="简体中文", value="zh"),
    ])
    async def slash_language(interaction: discord.Interaction, lang: app_commands.Choice[str]):
        # 获取服务器ID（如果是私聊则获取用户ID）
        guild_id = str(interaction.guild_id) if interaction.guild_id else str(interaction.user.id)

        # 保存语言设定
        save_server_language(guild_id, lang.value)

        if lang.value == "zh":
            await interaction.response.send_message("✅ 语言已成功切换为 **简体中文**！丛雨以后会用中文回复你们哦。")
        else:
            await interaction.response.send_message(
                "✅ Language has been set to **English**! Murasame will now reply in English.")
        logger.info(f"🌐 服务器 {guild_id} 将语言切换为 -> {lang.value}")

    # 👗 换装指令 (双语版)
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
            msg = f"👘 主人，我已经换上 **{clothing.name}** 啦！ *(这个状态会保持到下一次作息时间改变为止哦)*"
        else:
            msg = f"👘 Master, I've changed into my **{clothing.value}** outfit! *(Will persist until the next schedule change)*"

        await interaction.response.send_message(msg)
        logger.info(f"👗 [斜杠指令] 手动换装 -> {clothing.value}")

    # ❓ 帮助面板 (双语版)
    @bot.tree.command(name="help", description="Show the manual for Murasame Bot (查看使用说明)")
    async def slash_help(interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else str(interaction.user.id)
        current_lang = get_server_language(guild_id)

        if current_lang == "zh":
            embed = discord.Embed(title="🌸 丛雨 (Murasame) Bot 使用说明", description="主人，这是我的使用说明书哦！",
                                  color=discord.Color.brand_red())
            embed.add_field(name="💬 聊天", value="直接 `@我` 或者回复我的消息，就可以和我聊天啦！", inline=False)
            embed.add_field(name="👗 换衣服",
                            value="使用 `/outfit` 可以手动命令我换衣服，否则我会根据时间作息自己换衣服哦！", inline=False)
            embed.add_field(name="✨ 隐藏动作", value="在句子里加入 `摸头`, `喂食`, `抱抱`, `欺负` 试试看！",
                            inline=False)
            embed.add_field(name="🌐 切换语言", value="使用 `/language` 可以在本服务器切换中英双语模式。", inline=False)
        else:
            embed = discord.Embed(title="🌸 Murasame (丛雨) Bot Help",
                                  description="Here is how you can interact with me, Master!",
                                  color=discord.Color.brand_red())
            embed.add_field(name="💬 Chatting", value="Mention me (`@Murasame`) or reply to my messages to talk to me!",
                            inline=False)
            embed.add_field(name="👗 Changing Outfits",
                            value="Use the `/outfit` command to manually change my clothes. Otherwise, I will automatically change based on the time of day!",
                            inline=False)
            embed.add_field(name="✨ Secret Actions",
                            value="Try including words like `pat`, `headpat`, `feed`, `hug`, or `tease`!", inline=False)
            embed.add_field(name="🌐 Language",
                            value="Use `/language` to switch between English and Chinese in this server.", inline=False)

        embed.set_footer(text="Powered by Gemma & Discord.py")
        await interaction.response.send_message(embed=embed)