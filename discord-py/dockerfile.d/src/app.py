import os
import json
import logging

import requests
import discord
from discord import app_commands

APP_HOME = os.getenv("APP_HOME")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

handler = logging.FileHandler(
    filename=f"{APP_HOME}/discord.log", encoding="utf-8", mode="w"
)

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
logger = logging.getLogger("discord")


@tree.command(name="인사", description="인사합니다")
async def hello(interaction: discord.Interaction):
    log_data = {
        "interaction_id": interaction.id,
        "command": interaction.command.name if interaction.command else None,
        "user_id": interaction.user.id,
        "user_name": interaction.user.name,
        "channel_id": interaction.channel_id,
        "guild_id": interaction.guild_id,
        "guild_name": interaction.guild.name if interaction.guild else "DM",
        "locale": str(interaction.locale),
        "options": interaction.data.get("options", []) if interaction.data else [],
    }

    logger.info(json.dumps(log_data, ensure_ascii=False, default=str))

    await interaction.response.defer(ephemeral=True)

    try:
        requests.post(
            "http://n8n:5678/webhook/a9b918bb-26b1-4879-8b1e-b1304f92b112",
            data={
                "user_name": interaction.user.name,
                "guild_id": interaction.guild_id,
                "channel_id": interaction.channel_id,
            },
        )
        await interaction.followup.send(
            content="웹서버 요청 성공",
            ephemeral=True,
        )
    except Exception as e:
        logger.error(f"웹서버 요청 실패: {e}")
        await interaction.followup.send(f"웹서버 요청 실패")


@client.event
async def on_ready():
    await tree.sync()  # 글로벌 동기화
    logger.info("커맨드 동기화 완료!")


client.run(DISCORD_BOT_TOKEN, log_handler=handler)
