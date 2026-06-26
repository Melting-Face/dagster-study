import os
import json
import asyncio
import logging

import requests
import discord
from discord import app_commands
from ollama import chat, web_search, web_fetch

APP_HOME = os.getenv("APP_HOME")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Ollama Cloud 연동 설정
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "https://ollama.com")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:120b")

# Discord 메시지 1건 최대 길이
DISCORD_MAX_LEN = 2000


def split_message(text: str, limit: int = DISCORD_MAX_LEN) -> list[str]:
    """긴 텍스트를 Discord 길이 제한에 맞춰 여러 조각으로 나눈다.

    가능하면 줄 단위로 끊고, 한 줄이 limit을 넘으면 강제로 잘라 나눈다.
    """
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        # 한 줄 자체가 limit을 초과하면 강제로 분할
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        # 현재 조각에 줄을 추가하면 limit을 넘는 경우 조각을 확정
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks or [""]


async def send_chunks(interaction: discord.Interaction, text: str) -> None:
    """defer 이후의 응답을 길이 제한에 맞춰 여러 메시지로 분할 전송한다."""
    for chunk in split_message(text):
        await interaction.followup.send(content=chunk)


def query_ollama(prompt: str) -> str:
    """Ollama /api/chat 엔드포인트를 동기 호출해 응답 텍스트를 반환한다."""
    headers = {"Content-Type": "application/json"}
    # 클라우드(ollama.com) 사용 시 Bearer 인증 필요, 로컬은 키 없이 동작
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        headers=headers,
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def search_ollama(prompt: str) -> str:
    """웹서치 도구를 모델에 부여하고 tool-calling 루프를 돌려 답변을 반환한다.

    ollama 라이브러리는 OLLAMA_HOST/OLLAMA_API_KEY 환경변수를 자동으로 사용한다.
    """
    available_tools = {"web_search": web_search, "web_fetch": web_fetch}
    messages = [{"role": "user", "content": prompt}]

    # 무한 루프 방지를 위해 도구 호출 횟수를 제한한다
    for _ in range(5):
        response = chat(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=[web_search, web_fetch],
            # 검색 결과가 길어 컨텍스트를 넉넉히 확보한다
            options={"num_ctx": 32000},
        )
        messages.append(response.message)

        # 더 이상 도구 호출이 없으면 최종 답변 반환
        if not response.message.tool_calls:
            return response.message.content or ""

        # 모델이 요청한 도구를 실행해 결과를 다시 메시지에 추가한다
        for tool_call in response.message.tool_calls:
            function = available_tools.get(tool_call.function.name)
            if function is None:
                continue
            result = function(**tool_call.function.arguments)
            messages.append(
                {
                    "role": "tool",
                    "content": str(result),
                    "tool_name": tool_call.function.name,
                }
            )

    # 도구 호출 한도 초과 시 마지막 답변(없으면 안내) 반환
    return response.message.content or "검색 한도를 초과했습니다."


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


@tree.command(name="질문", description="Ollama LLM에게 질문합니다")
@app_commands.describe(prompt="LLM에게 보낼 질문 내용")
async def ask(interaction: discord.Interaction, prompt: str):
    log_data = {
        "interaction_id": interaction.id,
        "command": interaction.command.name if interaction.command else None,
        "user_id": interaction.user.id,
        "user_name": interaction.user.name,
        "channel_id": interaction.channel_id,
        "guild_id": interaction.guild_id,
        "model": OLLAMA_MODEL,
        "prompt": prompt,
    }
    logger.info(json.dumps(log_data, ensure_ascii=False, default=str))

    # LLM 응답은 3초를 넘기므로 먼저 응답을 지연시킨다
    await interaction.response.defer()

    try:
        # 동기 requests 호출이 이벤트 루프를 막지 않도록 별도 스레드에서 실행
        answer = await asyncio.to_thread(query_ollama, prompt)
        # Discord 길이 제한(2000자) 초과 시 여러 메시지로 분할 전송
        await send_chunks(interaction, answer)
    except Exception as e:
        logger.error(f"Ollama 요청 실패: {e}")
        await interaction.followup.send("Ollama 요청에 실패했습니다.")


@tree.command(name="검색", description="웹서치를 활용해 Ollama LLM에게 질문합니다")
@app_commands.describe(prompt="웹서치로 답변할 질문 내용")
async def search(interaction: discord.Interaction, prompt: str):
    log_data = {
        "interaction_id": interaction.id,
        "command": interaction.command.name if interaction.command else None,
        "user_id": interaction.user.id,
        "user_name": interaction.user.name,
        "channel_id": interaction.channel_id,
        "guild_id": interaction.guild_id,
        "model": OLLAMA_MODEL,
        "prompt": prompt,
    }
    logger.info(json.dumps(log_data, ensure_ascii=False, default=str))

    # 웹서치 + LLM 추론은 시간이 오래 걸리므로 먼저 응답을 지연시킨다
    await interaction.response.defer()

    try:
        # 동기 호출이 이벤트 루프를 막지 않도록 별도 스레드에서 실행
        answer = await asyncio.to_thread(search_ollama, prompt)
        # Discord 길이 제한(2000자) 초과 시 여러 메시지로 분할 전송
        await send_chunks(interaction, answer)
    except Exception as e:
        logger.error(f"Ollama 웹서치 요청 실패: {e}")
        await interaction.followup.send("Ollama 웹서치 요청에 실패했습니다.")


@client.event
async def on_ready():
    await tree.sync()  # 글로벌 동기화
    logger.info("커맨드 동기화 완료!")


client.run(DISCORD_BOT_TOKEN, log_handler=handler)
