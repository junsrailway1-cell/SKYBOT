# SKYBOT
import os
import io
import asyncio
import matplotlib.pyplot as plt
from typing import Optional, Literal
import re
import json
import sqlite3
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
import psutil
import json
import asyncio
from hypercorn.asyncio import serve
from hypercorn.config import Config

import aiohttp

import discord
from discord import app_commands
from discord.ext import tasks
from discord.ext import commands

from dotenv import load_dotenv
import requests
from datetime import datetime
from enum import Enum
import sqlite3
import random
import time

from discord.ui import View, button
from discord.ui import View, Button
from discord import ButtonStyle

from fastapi import FastAPI
import discord
from discord.ext import commands

from discord import Interaction
from discord import app_commands

from discord.ui import Modal, TextInput

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS community_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    author_id INTEGER,
    title TEXT,
    content TEXT,
    created_at TEXT
)
""")
conn.commit()

# 버전
cursor.execute("""
    CREATE TABLE IF NOT EXISTS version(
    id INTEGER PRIMARY KEY,
    n INTEGER,
    x INTEGER,
    y INTEGER
)
""")

# 패치로그
cursor.execute("""
    CREATE TABLE IF NOT EXISTS patch_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT,
    title TEXT,
    content TEXT,
    timestamp INTEGER
)

""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tictactoe_stats (
    userid INTEGER PRIMARY KEY,
    win    INTEGER DEFAULT 0,
    lose   INTEGER DEFAULT 0,
    draw   INTEGER DEFAULT 0
)
""")
conn.commit()

# 경제 히스토리
cursor.execute("""
    CREATE TABLE IF NOT EXISTS economy_history(
    user_id INTEGER,
    money INTEGER,
    level INTEGER,
    timestamp INTEGER
)

""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_version(
    id INTEGER PRIMARY KEY,
    major INTEGER,
    minor INTEGER,
    patch INTEGER
)
""")

cursor.execute("SELECT * FROM bot_version WHERE id=1")

if cursor.fetchone() is None:
    cursor.execute(
        "INSERT INTO bot_version VALUES (1,1,1,1)"
    )

conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_stats(
    hour TEXT PRIMARY KEY,
    messages INTEGER
)
""")

conn.commit()

cursor.execute("SELECT * FROM version WHERE id=1")

if cursor.fetchone() is None:
    cursor.execute(
        "INSERT INTO version VALUES (1,1,1,1)"
    )
    conn.commit()

app = FastAPI()

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents) 

conn = sqlite3.connect("economy.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS economy(
    user_id INTEGER PRIMARY KEY,
    money INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0,
    exp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1
)
""")

conn.commit()

def get_user(user_id):

    cur.execute("SELECT * FROM economy WHERE user_id=?", (user_id,))
    data = cur.fetchone()

    if data is None:
        cur.execute(
            "INSERT INTO economy (user_id,money,last_daily,exp,level) VALUES (?,0,0,0,1)",
            (user_id,)
        )
        conn.commit()
        return (user_id,0,0,0,1)

    return data

VERIFY_ROLE_ID = 1461636782176075831
UNVERIFY_ROLE_ID = 1478713261074550956
ADMIN_LOG_CHANNEL_ID = 1468191799855026208

ADDITIONAL_ADMIN_IDS = {
    794811652620156949,
    1246023821492752429,
    1185946251171217519,
    1206574701380636692
}

PAYOUT_ALLOWED_USER_IDS = {
    794811652620156949,
    1246023821492752429,
    1185946251171217519,
    1206574701380636692
}

emoji = {"<:X_red:1479810084900044851>",
          "<:_red:1479810110632099972>",
          "<:Log_blue:1479810216597127224>",
          "<:Chack_blue:1479810189434683402>",
          "<:announce_blue:1479810147911205006>",
          "<:verfired_green:1479810239619530752>"}

API_BASE = "https://web-api-production-091e.up.railway.app"

AUTO_BACKUP_MINUTES = 5


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_progress_bar(current: int, total: int, size: int = 20) -> str:
    if total <= 0:
        return f"{'░' * size} 0%"
    ratio = max(0, min(1, current / total))
    filled = int(ratio * size)
    return f"{'█' * filled}{'░' * (size - filled)} {int(ratio * 100)}%"


async def update_progress(interaction: discord.Interaction, title: str, current: int, total: int, detail: str):
    content = (
        f"## {title}\n"
        f"`{make_progress_bar(current, total)}`\n"
        f"진행: **{current}/{total}**\n"
        f"{detail}"
    )
    await interaction.edit_original_response(content=content)


def backup_file_path(guild_id: int) -> str:
    return f"{guild_id}.json"


def create_backup_data(guild: discord.Guild) -> dict:
    roles_data = []
    for role in guild.roles:
        if role.is_default():
            continue

        roles_data.append({
            "name": role.name,
            "color": role.color.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable,
            "permissions": role.permissions.value,
            "position": role.position
        })

    channels_data = []
    for channel in guild.channels:
        if isinstance(channel, discord.CategoryChannel):
            channel_type = "category"
            category_name = None
        elif isinstance(channel, discord.TextChannel):
            channel_type = "text"
            category_name = channel.category.name if channel.category else None
        elif isinstance(channel, discord.VoiceChannel):
            channel_type = "voice"
            category_name = channel.category.name if channel.category else None
        else:
            continue

        channels_data.append({
            "name": channel.name,
            "type": channel_type,
            "category": category_name,
            "position": channel.position
        })

    member_roles_data = {}
    for member in guild.members:
        role_names = [
            role.name
            for role in member.roles
            if not role.is_default() and not role.managed
        ]
        member_roles_data[str(member.id)] = role_names

    return {
        "guild_id": guild.id,
        "guild_name": guild.name,
        "created_at": now_iso(),
        "roles": sorted(roles_data, key=lambda x: x["position"]),
        "channels": sorted(channels_data, key=lambda x: x["position"]),
        "member_roles": member_roles_data
    }


def save_backup_data(guild: discord.Guild) -> str:
    data = create_backup_data(guild)
    file_path = backup_file_path(guild.id)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return file_path


def load_backup_data(guild_id: int):
    file_path = backup_file_path(guild_id)
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@tasks.loop(minutes=AUTO_BACKUP_MINUTES)
async def auto_backup_loop():
    for guild in bot.guilds:
        try:
            save_backup_data(guild)
            print(f"[자동백업 완료] {guild.name} ({guild.id})")
        except Exception as e:
            print(f"[자동백업 실패] {guild.name} ({guild.id}) -> {e}")

def increase_version():

    cur.execute("SELECT major, minor, patch FROM bot_version WHERE id=1")
    major, minor, patch = cur.fetchone()

    patch += 1

    if patch > 9:
        patch = 0
        minor += 1

    cur.execute(
        "UPDATE bot_version SET major=?, minor=?, patch=? WHERE id=1",
        (major, minor, patch)
    )

    conn.commit()

    return f"{major}.{minor}.{patch}"

def get_guild_group_id(guild_id: int):
    cursor.execute(
        "SELECT group_id FROM group_settings WHERE guild_id=?",
        (guild_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else None

def is_already_verified(guild_id: int, user_id: int) -> bool:
    try:
        resp = requests.get(
            f"{API_BASE}/api/logs/verify",
            params={
                "guild_id": guild_id,
                "user_id": user_id,
                "limit": 1,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            print("[WEB_CHECK_ERROR]", resp.status_code, resp.text)
            return False 

        data = resp.json()
        return len(data) > 0
    except Exception as e:
        print("[WEB_CHECK_EXCEPTION]", repr(e))
        return False
    
LOG_API_URL = "https://web-api-production-69fc.up.railway.app"

COMMANDS_DISABLED = False

DEVELOPER_ID = 1276176866440642561 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR) 

env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path) 

OFFICER_ROLE_ID = 1477313558474920057
TARGET_ROLE_ID = 1461636782176075831 

TOKEN = str(os.getenv("DISCORD_TOKEN"))
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
OWNER_ID = int(os.getenv("OWNER_ID", "0")) 

RANK_API_URL_ROOT = "https://surprising-perfection-production-e015.up.railway.app"
print("DEBUG ROOT:", repr(RANK_API_URL_ROOT))
RANK_API_KEY = os.getenv("RANK_API_KEY") 

CREATOR_ROBLOX_NICK = "Sky_Lunarx"
CREATOR_ROBLOX_REAL = "Sky_Lunarx"
CREATOR_DISCORD_NAME = "Lunar"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def is_toxic(text: str) -> tuple[bool, list[str]]:
    if not OPENAI_API_KEY:
        return False, []

    url = "https://api.openai.com/v1/moderations"
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "omni-moderation-latest",
        "input": [{"type": "text", "text": text}],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()["results"][0]
    flagged = result["flagged"]
    categories = [k for k, v in result["categories"].items() if v]
    return flagged, categories

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN이 .env에 설정되어 있지 않습니다.") 

intents = discord.Intents.all() 

error_logs: list[dict] = []
MAX_LOGS = 50

HELP_CATEGORIES: dict[str, dict] = {
    "일반": {
        "emoji": "📦",
        "commands": [
            ("/도움말", "이 도움말을 보여줍니다."),
            ("/버전", "현재 봇 버전을 확인합니다."),
            ("/패치공지", "패치 공지를 작성합니다."),
            ("/채팅그래프", "최근 채팅량을 그래프로 확인합니다."),
            ("/동기화", "슬래시 명령어를 동기화합니다."),
            ("/핑", "봇의 지연 시간을 확인합니다."),
            ("/서버핑", "봇의 웹소켓 핑을 확인합니다."),
            ("/서버정보", "서버 기본 정보를 보여줍니다."),
            ("/서버시간", "현재 UTC/KST 시간을 보여줍니다."),
            ("/서버통계", "서버 인원 통계를 간단히 보여줍니다."),
            ("/서버생성", "이 서버의 생성일을 확인합니다."),
            ("/봇정보", "봇의 기본 정보를 보여줍니다."),
        ],
    },

    "인증": {
        "emoji": "✅",
        "commands": [
            ("/인증", "로블록스 계정 인증을 시작합니다."),
            ("/일괄강제인증", "서버의 모든 미인증자를 강제 인증 처리합니다. (제작자 전용)"),
            ("/강제인증", "유저를 강제로 인증 처리합니다. (관리자)"),
            ("/강제인증해제", "특정 유저의 강제 인증을 해제합니다. (관리자)"),
            ("/인증로그보기", "인증 기록을 확인합니다. (관리자)"),
            ("/인증통계", "서버 인증 통계를 보여줍니다."),
        ],
    },

    "경제": {
        "emoji": "💰",
        "commands": [
            ("/돈", "24시간마다 돈을 받습니다."),
            ("/도박", "돈을 걸고 도박합니다."),
            ("/극적도박", "극적인(고위험) 도박을 합니다."),
            ("/아이템샵", "서버 아이템을 보여줍니다."),
            ("/구매", "상점 아이템을 구매합니다."),
            ("/잭팟", "현재 잭팟 금액을 확인합니다."),
            ("/내경제", "내 경제 정보를 요약해서 보여줍니다."),
            ("/내순위", "내 경제 랭킹 위치를 확인합니다."),
            ("/랭킹", "서버 경제 랭킹을 보여줍니다."),
            ("/송금", "다른 유저에게 돈을 송금합니다."),
            ("/경제그래프", "경제 그래프를 확인합니다."),
            ("/경제백업", "경제 데이터를 JSON으로 백업합니다."),
            ("/경제백업다운로드", "경제 백업 파일을 다운로드합니다."),
            ("/경제초기화", "경제 데이터를 초기화합니다. (제작자)"),
            ("/돈추가", "유저에게 돈을 추가합니다. (관리자)"),
            ("/돈제거", "유저의 돈을 제거합니다. (관리자)"),
            ("/레벨추가", "유저 레벨을 추가합니다."),
        ],
    },

    "상점 관리": {
        "emoji": "🛒",
        "commands": [
            ("/아이템추가", "상점 아이템을 추가합니다. (관리자)"),
            ("/아이템삭제", "상점에서 아이템을 삭제합니다. (관리자)"),
        ],
    },

    "공지/시스템": {
        "emoji": "📢",
        "commands": [
            ("/공지", "인증된 모든 유저에게 공지를 전송합니다."),
            ("/페이아웃", "로블닉으로 1회 그룹 페이아웃을 진행합니다."),
            ("/서버공지", "지정한 채널에 공지 임베드를 전송합니다."),
        ],
    },

    "경고/처벌/유저": {
        "emoji": "⚠️",
        "commands": [
            ("/경고", "유저에게 경고를 1회 부여합니다. (관리자)"),
            ("/처벌추가", "경고 횟수에 따른 처벌 규칙을 추가합니다. (관리자)"),
            ("/유저", "유저 정보를 확인합니다."),
            ("/유저관리", "특정 유저를 경고/제재/정보 조회 등으로 관리합니다."),
        ],
    },

    "로그/설정": {
        "emoji": "📝",
        "commands": [
            ("/로그채널지정", "로그 채널을 설정합니다. (관리자)"),
            ("/명령어로그", "명령어 사용 기록을 확인합니다. (관리자)"),
            ("/관리자지정", "관리자 역할을 추가/제거합니다. (개발자 전용)"),
            ("/권한목록", "서버 역할들의 위험 권한을 페이지로 확인합니다."),
            ("/역할목록", "서버 역할과 봇 역할을 10개씩 출력합니다. (관리자)"),
        ],
    },

    "블랙리스트": {
        "emoji": "⛔",
        "commands": [
            ("/블랙리스트", "블랙리스트 그룹을 관리합니다. (관리자)"),
            ("/블랙리스트목록", "블랙리스트 그룹 목록을 봅니다. (관리자)"),
        ],
    },

    "그룹/랭크": {
        "emoji": "🎖️",
        "commands": [
            ("/명단", "Roblox 그룹 역할 리스트를 보여줍니다."),
            ("/승진", "Roblox 그룹 랭크를 특정 역할로 변경합니다. (관리자)"),
            ("/강등", "Roblox 그룹 랭크를 특정 역할로 변경합니다. (관리자)"),
            ("/일괄승진", "인증된 모든 유저를 특정 역할로 승진합니다. (관리자)"),
            ("/일괄강등", "인증된 모든 유저를 특정 역할로 강등합니다. (관리자)"),
        ],
    },
    
    "유저•편의": {
        "emoji": "👤",
        "commands": [
            ("/내정보", "내 경제/경고/인증 정보를 한 번에 확인합니다."),
            ("/유저정보", "특정 유저의 정보와 상태를 확인합니다."),
            ("/내아이디", "내 디스코드 ID를 확인합니다."),
            ("/유저아이디", "특정 유저의 디스코드 ID를 확인합니다."),
            ("/아이디", "지정한 유저 또는 내 ID를 확인합니다."),
            ("/아바타", "유저의 프로필 이미지를 크게 보여줍니다."),
            ("/내가입", "이 서버에 내가 언제 들어왔는지 확인합니다."),
            ("/내역할", "내가 가지고 있는 역할 목록을 보여줍니다."),
            ("/닉변경", "내 닉네임 또는 (관리자일 때) 다른 유저 닉네임을 변경합니다."),
            ("/귓", "특정 유저에게 DM을 보냅니다."),
        ],
    },

    "역할/링크/관리": {
        "emoji": "🛠️",
        "commands": [
            ("/청소", "최근 메시지를 정리합니다. (관리자/메시지 관리)"),
            ("/역할지급", "유저에게 역할을 추가하거나 제거합니다. (관리자)"),
            ("/일괄역할추가", "여러 유저에게 역할을 한 번에 추가합니다. (관리자)"),
            ("/일괄역할삭제", "여러 유저에게서 역할을 한 번에 제거합니다. (관리자)"),
            ("/역할삭제", "서버에서 특정 역할 자체를 삭제합니다. (관리자)"),
            ("/서버역할", "서버 역할 목록을 간단히 보여줍니다."),
            ("/서버링크", "현재 채널의 초대 링크를 생성합니다."),
            ("/링크보기", "서버 초대 링크 목록을 확인합니다."),
        ],
    },
}

DB_PATH = os.path.join(BASE_DIR, "bot.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor() 

cursor.execute("""
CREATE TABLE IF NOT EXISTS transfer_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    from_id INTEGER,
    to_id INTEGER,
    amount INTEGER,
    created_at TEXT
)
""")
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS mod_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    user_id INTEGER,
    action TEXT,        -- 'warn', 'ban', 'kick', 'timeout', 'mute' 등
    moderator_id INTEGER,
    reason TEXT,
    created_at TEXT     -- ISO 또는 datetime('now')
)
""")
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    guild_id INTEGER,
    user_id INTEGER,
    warns INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS punish_rules (
    guild_id INTEGER,
    warn_count INTEGER,
    punish_type TEXT,      -- 'ban', 'timeout', 'mute', 'kick'
    duration INTEGER,      -- 초 (timeout/mute일 때만 사용, 나머지는 NULL 가능)
    PRIMARY KEY (guild_id, warn_count)
)
""")
conn.commit()

cursor.execute(
    """CREATE TABLE IF NOT EXISTS rank_log_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        log_data TEXT,
        created_at TEXT
    )"""
)
conn.commit() 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS senior_officer_settings(
        guild_id INTEGER PRIMARY KEY,
        senior_officer_role_id INTEGER
    )"""
)
conn.commit() 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS blacklist(
        guild_id INTEGER,
        group_id INTEGER,
        PRIMARY KEY(guild_id, group_id)
    )"""
)
conn.commit() 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS rank_log_settings(
        guild_id INTEGER PRIMARY KEY,
        channel_id INTEGER,
        enabled INTEGER DEFAULT 0
    )"""
)
conn.commit() 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS forced_verified(
        discord_id INTEGER,
        guild_id INTEGER,
        roblox_nick TEXT,
        roblox_user_id INTEGER,
        rank_role TEXT,
        PRIMARY KEY(discord_id, guild_id)
    )"""
)
conn.commit() 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS users(
        discord_id INTEGER,
        guild_id INTEGER,
        roblox_nick TEXT,
        roblox_user_id INTEGER,
        code TEXT,
        expire_time TEXT,
        verified INTEGER DEFAULT 0,
        PRIMARY KEY(discord_id, guild_id)
    )"""
) 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS stats(
        guild_id INTEGER PRIMARY KEY,
        verify_count INTEGER DEFAULT 0,
        force_count INTEGER DEFAULT 0,
        cancel_count INTEGER DEFAULT 0
    )"""
) 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS settings(
        guild_id INTEGER PRIMARY KEY,
        role_id INTEGER,
        status_channel_id INTEGER,
        admin_role_id TEXT
    )"""
) 

cur.execute("""
CREATE TABLE IF NOT EXISTS jackpot (
    id INTEGER PRIMARY KEY,
    money INTEGER
)
""")

cur.execute("INSERT OR IGNORE INTO jackpot (id, money) VALUES (1,0)")
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS logchannels (
    guildid   INTEGER,
    logtype   TEXT,
    channelid INTEGER,
    PRIMARY KEY (guildid, logtype)
)
""")
conn.commit() 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS officer_settings(
        guild_id INTEGER PRIMARY KEY,
        officer_role_id INTEGER
    )"""
)
conn.commit() 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS group_settings(
        guild_id INTEGER PRIMARY KEY,
        group_id INTEGER
    )"""
) 

cursor.execute(
    """CREATE TABLE IF NOT EXISTS rollback_settings(
        guild_id INTEGER PRIMARY KEY,
        auto_rollback INTEGER DEFAULT 1
    )"""
)
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS shop_items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    name TEXT,
    price INTEGER,
    type TEXT,          -- 'role', 'level', 'exp'
    role_id INTEGER,    -- type='role' 일 때만 사용
    level INTEGER,      -- type='level' 일 때만 사용
    exp INTEGER         -- type='exp' 일 때만 사용
)
""")
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS command_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    user_id INTEGER,
    user_name TEXT,
    command_name TEXT,
    command_full TEXT,
    created_at TEXT
)
""")
conn.commit()

conn.commit()

class MemberListView(discord.ui.View):
    def __init__(self, title: str, lines: list[str]):
        super().__init__(timeout=60)
        self.title = title
        self.lines = lines
        self.index = 0
        self.per_page = 10

    def make_page_embed(self) -> discord.Embed:
        start = self.index * self.per_page
        end = start + self.per_page
        chunk = self.lines[start:end]

        desc = "\n".join(chunk) if chunk else "표시할 유저가 없습니다."
        embed = discord.Embed(
            title=f"{self.title} ({self.index + 1}/{self.max_page})",
            description=desc,
            color=discord.Color.dark_blue(),
        )
        return embed

    @property
    def max_page(self) -> int:
        return max(1, (len(self.lines) + self.per_page - 1) // self.per_page)

    async def update(self, interaction: discord.Interaction):
        embed = self.make_page_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅ 이전", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            await self.update(interaction)

    @discord.ui.button(label="다음 ➡", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index < self.max_page - 1:
            self.index += 1
            await self.update(interaction)
                   
class HelpView(discord.ui.View):
    def __init__(self, user: discord.abc.User):
        super().__init__(timeout=120)
        self.user = user
        self.category_keys = list(HELP_CATEGORIES.keys())
        self.index = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    @property
    def max_page(self) -> int:
        return len(self.category_keys)

    def make_page_embed(self) -> discord.Embed:
        key = self.category_keys[self.index]
        data = HELP_CATEGORIES[key]
        emoji = data["emoji"]
        commands = data["commands"]

        lines = [f"**{name}** — {desc}" for name, desc in commands]
        desc = "\n".join(lines) if lines else "등록된 명령어가 없습니다."

        embed = discord.Embed(
            title=f"{emoji} {key} 명령어 ({self.index + 1}/{self.max_page})",
            description=desc,
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"요청자: {self.user}", icon_url=self.user.display_avatar.url)
        return embed

    async def update(self, interaction: discord.Interaction):
        embed = self.make_page_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅ 이전", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            await self.update(interaction)

    @discord.ui.button(label="다음 ➡", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index < self.max_page - 1:
            self.index += 1
            await self.update(interaction)
            
class RolePermsView(discord.ui.View):
    def __init__(self, roles: list[discord.Role]):
        super().__init__(timeout=60)
        self.roles = roles
        self.index = 0
        self.per_page = 10

    def make_page_embed(self) -> discord.Embed:
        start = self.index * self.per_page
        end = start + self.per_page
        chunk = self.roles[start:end]

        lines = []
        flags = [
            ("관리자", "administrator"),
            ("서버 관리", "manage_guild"),
            ("역할 관리", "manage_roles"),
            ("채널 관리", "manage_channels"),
            ("멤버 추방", "kick_members"),
            ("멤버 차단", "ban_members"),
            ("메시지 관리", "manage_messages"),
            ("@everyone 멘션", "mention_everyone"),
        ]

        for role in chunk:
            perms = [
                name for name, attr in flags
                if getattr(role.permissions, attr, False)
            ]
            perm_text = ", ".join(perms) if perms else "중요 권한 없음"
            lines.append(f"{role.mention} (`{role.id}`)\n→ {perm_text}")

        desc = "\n\n".join(lines) if lines else "표시할 역할이 없습니다."

        embed = discord.Embed(
            title=f"역할 권한 목록 ({self.index + 1}/{self.max_page})",
            description=desc,
            color=discord.Color.blurple(),
        )
        return embed

    @property
    def max_page(self) -> int:
        return max(1, (len(self.roles) + self.per_page - 1) // self.per_page)

    async def update(self, interaction: discord.Interaction):
        embed = self.make_page_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅ 이전", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            await self.update(interaction)

    @discord.ui.button(label="다음 ➡", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index < self.max_page - 1:
            self.index += 1
            await self.update(interaction)
            
    async def on_submit(self, interaction: discord.Interaction):
        content = self.content_input.value

        # AI 악성 검사
        flagged, categories = is_toxic(content)
        if flagged:
            msg = "해당 내용은 이용 수칙을 위반하여 등록이 차단되었습니다.\n"
            if categories:
                msg += f"감지된 항목: {', '.join(categories)}"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        guild_id = interaction.guild.id if interaction.guild else 0

        cursor.execute(
            "INSERT INTO community_posts (guild_id, author_id, title, content, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (
                guild_id,
                interaction.user.id,
                self.title_input.value,
                content,
            ),
        )
        conn.commit()
        post_id = cursor.lastrowid

        embed = discord.Embed(
            title=f"커뮤니티 양식 제출 완료 (#{post_id})",
            description=content,
            color=discord.Color.blurple()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.add_field(name="제목", value=self.title_input.value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        
class GroupUserView(discord.ui.View):
    def __init__(self, group_id, role_id, users, next_cursor, prev_cursor):
        super().__init__(timeout=60)
        self.group_id = group_id
        self.role_id = role_id
        self.users = users
        self.next_cursor = next_cursor
        self.prev_cursor = prev_cursor

    def make_embed(self):
        lines = []

        for user in self.users:
            lines.append(f"• {user['username']} (`{user['userId']}`)")

        desc = "\n".join(lines) if lines else "유저 없음"

        embed = discord.Embed(
            title="👥 그룹 역할 유저 목록",
            description=desc,
            color=discord.Color.blurple()
        )

        return embed

    async def update(self, interaction, cursor):
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://groups.roblox.com/v1/groups/{self.group_id}/roles/{self.role_id}/users?limit=10&cursor={cursor}"
            ) as resp:

                data = await resp.json()

        self.users = data["data"]
        self.next_cursor = data["nextPageCursor"]
        self.prev_cursor = data["previousPageCursor"]

        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self
        )

    @discord.ui.button(label="⬅ 이전", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, _):
        if self.prev_cursor:
            await self.update(interaction, self.prev_cursor)

    @discord.ui.button(label="다음 ➡", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, _):
        if self.next_cursor:
            await self.update(interaction, self.next_cursor)

class CommandLogView(View):
    def __init__(self, pages: list[str]):
        super().__init__(timeout=60)
        self.pages = pages
        self.index = 0

    async def update(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📜 명령어 로그",
            description=self.pages[self.index],
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"페이지 {self.index+1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="⬅ 이전", style=ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
        await self.update(interaction)

    @button(label="다음 ➡", style=ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index < len(self.pages) - 1:
            self.index += 1
        await self.update(interaction)

def get_senior_officer_role_id(guild_id: int) -> Optional[int]:
    cursor.execute("SELECT senior_officer_role_id FROM senior_officer_settings WHERE guild_id=?", (guild_id,))
    row = cursor.fetchone()
    return row[0] if row else None 

def set_senior_officer_role_id(guild_id: int, role_id: int) -> None:
    cursor.execute(
        """INSERT OR REPLACE INTO senior_officer_settings(guild_id, senior_officer_role_id)
           VALUES(?, ?)""",
        (guild_id, role_id),
    )
    conn.commit()
    
def check_is_officer(rank_num: int, rank_name: str) -> tuple[bool, bool]:
    """위관급, 영관급 여부 체크 - (is_junior_officer, is_senior_officer)"""
    
    is_junior = 70 <= rank_num <= 120
    junior_keywords = ["Second Lieutenant", "First Lieutenant", "Captain", "Major", "Lieutenant Colonel", "소위", "중위", "대위", "소령", "중령"]
    if any(kw.lower() in rank_name.lower() for kw in junior_keywords):
        is_junior = True
        
    is_senior = 130 <= rank_num <= 170
    senior_keywords = [
        "Colonel", "Brigadier General", "Major General", "Lieutenant General", "General", 
        "대령", "준장", "소장", "중장", "대장", "원수"
    ]
    if any(kw.lower() in rank_name.lower() for kw in senior_keywords):
        is_senior = True
    
    return (is_junior, is_senior) 

LOG_DIR = os.environ.get("LOG_DIR", "/app/logs")
os.makedirs(LOG_DIR, exist_ok=True) 

def save_verification_log(discord_nick: str, roblox_nick: str):
    """인증 성공 시 로그 파일에 기록 + 콘솔에 같이 출력"""
    log_file = os.path.join(LOG_DIR, "verification_log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{discord_nick}]: [{roblox_nick}]" 
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n") 
        print("[VERIFY_LOG]", line)
        print("/인증 로블닉:{}")
    except Exception as e:
        print(f"로그 저장 실패: {e}")
        
@bot.tree.command(name="공지전송", description="고정 공지를 채널에 전송")
async def notice_send(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("권한이 없습니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    msg1 = """# [ 디스코드 닉네임 양식 ]

[계급] (보직) 로블록스 닉네임

가입 한 보직이 없을 경우 보직란은 작성하지 않습니다.

보직별 보직란에 적어야 할 영어는 다음과 같습니다.

<@&1497820313180704880> : HQ
<@&1497826757250908241> : SWC
<@&1497828663888973915> : 13th SMB
<@&1497828665692524606> : 9th SFB

만약 로블록스 닉네임이 너무 길어서 작성이 되지 않을 시, <@1206574701380636692> 에게 도움을 요청하세요."""
    
    msg2 = """## 진급 방법
시험 범위
소위부터 대위는 훈련병부터 원사 시험까지 가능
소령부터는 준위 시험까지 가능

훈련병: 훈련병 시험 통과 및 보직 계급 배치
이등병: 이등병 시험 통과 및 보직 계급 배치
일등병: 일등병 시험 통과 및 보직 계급 배치
상등병: 상등병 시험 통과 및 보직 계급 배치
분대장: 분대장 시험 통과 및 보직 계급 배치
병장: 병장 시험 통과
하사: 하사 시험 통과
중사: 중사 시험 통과
상사: 상사 시험 통과
원사: 원사 시험 통과
준위: 준위 시험 통과

소위: 병사진급제 (육군본부에서 시행)
중위: 병사진급제 (육군본부에서 시행)
대위: 병사진급제 (육군본부에서 시행)
소령: 병사진급제 (육군본부에서 시행)
중령: 병사진급제 (육군본부에서 시행)
대령: 병사진급제 (육군본부에서 시행)

준장: 군 수뇌부 회의 결과로 특진
소장: 군 수뇌부 회의 결과로 특진
중장: 군 수뇌부 회의 결과로 특진

대장: 육군주임원사 선거 당선

육군주임원사: 육군참모차장 선거 당선
육군참모차장: 육군참모총장 선거 당선
육군참모총장: 군 수뇌부 회의 결과로 특진
합동참모의장: 군 수뇌부 회의 결과로 특진
국방부장관: 군 수뇌부 회의 결과로 특진

국무총리: 국군통수권자의 통수권 이양

선거 방식
소장부터 육군주임원사 선거 지원 가능
중장부터 육군참모차장 선거 지원 가능
대장부터 육군참모총장 선거 지원 가능

선거 지원자 중 후보자 선별 (최대 3명)"""

    msg3 = """**모든 행정의 중심, 스카이부대 직속예하 최상위 지휘본부**
# '육군본부'
https://discord.gg/nryVxmUXn3

@everyone"""

    data = [
        (1461636785250504760, msg1),
        (1472449849575211097, msg2),
        (1497955213787795667, msg3),
    ]

    success = 0
    failed = []

    for channel_id, text in data:
        try:
            channel = interaction.guild.get_channel(channel_id)
            if channel is None:
                channel = await interaction.guild.fetch_channel(channel_id)

            await channel.send(text)
            success += 1
        except Exception as e:
            failed.append(f"{channel_id}: {e}")

    result = f"완료됨. 성공 {success}개"
    if failed:
        result += "\\n실패:\\n" + "\\n".join(failed[:10])

    await interaction.followup.send(result, ephemeral=True)

@bot.command(name="폴더")
@commands.has_permissions(ban_members=True)
async def ban_command(
    ctx: commands.Context,
    member: discord.Member | None = None,
    *, reason: str | None = None,
):
    if member is None:
        await ctx.send("밴할 유저를 멘션해 주세요. 예: `!밴 @유저 스팸`")
        return

    if member == ctx.author:
        await ctx.send("자기 자신은 밴할 수 없습니다.")
        return

    if member.top_role >= ctx.author.top_role:
        await ctx.send("자신보다 같거나 높은 역할을 가진 유저는 밴할 수 없습니다.")
        return

    if member.top_role >= ctx.guild.me.top_role:
        await ctx.send("제가 관리할 수 없는 역할을 가진 유저입니다.")
        return

    try:
        await member.ban(reason=reason or f"Banned by {ctx.author}")
        await ctx.send(f"{member.mention} 님을 밴했습니다. 사유: {reason or '사유 없음'}")
    except discord.Forbidden:
        await ctx.send("권한이 부족해서 밴할 수 없습니다.")
    except Exception as e:
        await ctx.send(f"밴 중 오류가 발생했습니다: {e}")
        
@app_commands.default_permissions(administrator=True)
@bot.tree.command(name="권한목록", description="서버 역할들의 위험 권한을 페이지로 확인합니다.")
async def 권한목록(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    roles = [r for r in guild.roles if not r.is_default()]
    roles.sort(key=lambda r: r.position, reverse=True)

    view = RolePermsView(roles)
    embed = view.make_page_embed()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
class CommunityFormModal(Modal, title="커뮤니티 양식 제출"):
    title_input = TextInput(
        label="제목",
        placeholder="제목을 입력하세요",
        max_length=100
    )
    content_input = TextInput(
        label="내용",
        style=discord.TextStyle.paragraph,
        placeholder="내용(양식)에 맞게 적어 주세요",
        max_length=2000
    )

def set_guild_group_id(guild_id: int, group_id: int) -> None:
    cursor.execute(
        """
        INSERT INTO group_settings(guild_id, group_id)
        VALUES(?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET group_id=excluded.group_id
        """,
        (guild_id, group_id),
    )
    conn.commit()


def get_guild_role_id(guild_id: int) -> Optional[int]:
    cursor.execute("SELECT role_id FROM settings WHERE guild_id=?", (guild_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def set_guild_role_id(guild_id: int, role_id: int) -> None:
    cursor.execute(
        """
        INSERT INTO settings(guild_id, role_id)
        VALUES(?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET role_id=excluded.role_id
        """,
        (guild_id, role_id),
    )
    conn.commit()

async def send_admin_log(
    guild: discord.Guild,
    title: str,
    description: str | None = None,
    color: discord.Color = discord.Color.blurple(),
    fields: list[tuple[str, str, bool]] | None = None,
):
    log_ch_id = get_log_channel(guild.id, "admin")
    if not log_ch_id:
        return

    channel = guild.get_channel(log_ch_id) or await guild.fetch_channel(log_ch_id)
    if not channel:
        return

    embed = discord.Embed(title=title, color=color, description=description)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

    embed.set_footer(text="관리자 로그")
    await channel.send(embed=embed)

def set_log_channel(guild_id: int, log_type: str, channel_id: int | None):
    if channel_id is None:
        cursor.execute(
            "DELETE FROM logchannels WHERE guildid=? AND logtype=?",
            (guild_id, log_type),
        )
    else:
        cursor.execute(
            """
            INSERT INTO logchannels(guildid, logtype, channelid)
            VALUES (?, ?, ?)
            ON CONFLICT(guildid, logtype)
            DO UPDATE SET channelid=excluded.channelid
            """,
            (guild_id, log_type, channel_id),
        )
    conn.commit() 

def get_log_channel(guild_id: int, log_type: str) -> int | None:
    cursor.execute(
        "SELECT channelid FROM logchannels WHERE guildid=? AND logtype=?",
        (guild_id, log_type),
    )
    row = cursor.fetchone()
    return row[0] if row else None 

def get_guild_admin_role_ids(guild_id: int) -> list[int]:
    cursor.execute("SELECT admin_role_id FROM settings WHERE guild_id=?", (guild_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        return []
    try:
        import json 

        if isinstance(row[0], str):
            return list(map(int, json.loads(row[0])))
        return [int(row[0])]
    except Exception:
        return []


def set_guild_admin_role_ids(guild_id: int, role_ids: list[int]) -> None:
    import json 

    value = json.dumps(role_ids)
    cursor.execute(
        """
        INSERT INTO settings(guild_id, admin_role_id)
        VALUES(?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET admin_role_id=excluded.admin_role_id
        """,
        (guild_id, value),
    )
    conn.commit()


def is_owner(user: discord.abc.User | discord.Member) -> bool:
    if OWNER_ID <= 0:
        return False
    return int(user.id) == int(OWNER_ID)


def is_admin(member: discord.Member) -> bool:
    if is_owner(member):
        return True 
    try:
        if member.guild_permissions.administrator:
            return True
    except AttributeError:
        return False 
    guild = member.guild
    if guild is None:
        return False 

    admin_ids = get_guild_admin_role_ids(guild.id)
    if not admin_ids:
        return False 

    member_role_ids = {r.id for r in member.roles}
    if any(rid in member_role_ids for rid in admin_ids):
        return True 

    return False 

def _rank_api_headers():
    return {
        "Content-Type": "application/json",
        "X-API-KEY": RANK_API_KEY,
    } 

def add_error_log(error_msg: str) -> None:
    error_logs.append({"timestamp": datetime.now(timezone.utc), "message": error_msg})
    if len(error_logs) > MAX_LOGS:
        error_logs.pop(0)


def generate_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8)) 
ROBLOX_USERNAME_API = "https://users.roblox.com/v1/usernames/users"
ROBLOX_USER_API = "https://users.roblox.com/v1/users/{userId}"


async def roblox_get_user_id_by_username(username: str) -> Optional[int]:
    payload = {"usernames": [username], "excludeBannedUsers": True}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                ROBLOX_USERNAME_API,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                results = data.get("data", [])
                return results[0].get("id") if results else None
        except Exception as e:
            add_error_log(f"roblox_get_user_id: {repr(e)}")
            return None 

async def roblox_get_user_groups(user_id: int) -> list[int]:
    """사용자가 속한 Roblox 그룹 ID 목록을 반환합니다."""
    url = f"https://groups.roblox.com/v2/users/{user_id}/groups/roles"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    print(
                        f"DEBUG: Roblox API error for user {user_id}: "
                        f"status {resp.status}"
                    )
                    return [] 

                data = await resp.json()
                print(f"DEBUG: Roblox API response for {user_id}: {data}") 

                groups = data.get("data", [])
                group_ids = [
                    g.get("group", {}).get("id")
                    for g in groups
                    if g.get("group")
                ]
                print(f"DEBUG: Extracted group_ids: {group_ids}")
                return group_ids
        except Exception as e:
            add_error_log(f"roblox_get_user_groups: {repr(e)}")
            print(f"DEBUG: Exception in roblox_get_user_groups: {e}")
            return [] 
        
async def apply_punishment(
    guild: discord.Guild,
    member: discord.Member,
    punish_type: str,
    duration: int | None,
    executor: discord.Member | discord.User,
    reason: str | None,
):
    reason_text = reason or f"자동 처벌 (by {executor})"

    if punish_type == "ban":
        await guild.ban(member, reason=reason_text)
    elif punish_type == "kick":
        await guild.kick(member, reason=reason_text)
    elif punish_type == "timeout":
        if duration and duration > 0:
            await member.timeout(timedelta(seconds=duration), reason=reason_text)
    elif punish_type == "mute":
        mute_role_id = ...
        mute_role = guild.get_role(mute_role_id)
        if mute_role:
            await member.add_roles(mute_role, reason=reason_text)

async def roblox_get_description_by_user_id(user_id: int) -> Optional[str]:
    url = ROBLOX_USER_API.format(userId=user_id)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("description")
        except Exception as e:
            add_error_log(f"roblox_get_description: {repr(e)}")
            return None
        
def get_officer_role_id(guild_id: int) -> Optional[int]:
    cursor.execute("SELECT officer_role_id FROM officer_settings WHERE guild_id=?", (guild_id,))
    row = cursor.fetchone()
    return row[0] if row else None 

def set_officer_role_id(guild_id: int, role_id: int) -> None:
    cursor.execute(
        """INSERT OR REPLACE INTO officer_settings(guild_id, officer_role_id)
           VALUES(?, ?)""",
        (guild_id, role_id),
    )
    conn.commit()

class VerifyView(discord.ui.View):
    def __init__(self, code: str, expire_time: datetime, guild_id: int):
        super().__init__(timeout=300)
        self.code = code
        self.expire_time = expire_time
        self.guild_id = guild_id 

def get_version():

    cursor.execute("SELECT n,x,y FROM version WHERE id=1")
    n,x,y = cursor.fetchone()

    return f"{n}.{x}.{y}"

def calc_server_security_score(guild: discord.Guild) -> tuple[int, list[str]]:
    """
    서버 보안 점수(0~100)를 계산하고, 개선이 필요한 항목 설명 리스트를 함께 반환합니다.
    """
    score = 100
    reasons: list[str] = []

    # 1. 서버 보안 레벨 (2FA 등)
    #   - DISABLED: -15
    #   - LOW: -10
    #   - MEDIUM: -5
    #   - HIGH 이상: 0
    lvl = guild.verification_level
    if lvl.name in ("NONE", "LOW"):
        score -= 15
        reasons.append("서버 보안 레벨이 낮습니다. (설정 > 커뮤니티 > 보안 레벨)")
    elif lvl.name == "MEDIUM":
        score -= 5

    # 2. @everyone 권한 체크
    everyone = guild.default_role
    perms = everyone.permissions
    bad_everyone = []
    if perms.administrator:
        bad_everyone.append("관리자")
    if perms.manage_guild:
        bad_everyone.append("서버 관리")
    if perms.manage_roles:
        bad_everyone.append("역할 관리")
    if perms.manage_channels:
        bad_everyone.append("채널 관리")
    if perms.ban_members or perms.kick_members:
        bad_everyone.append("밴/킥")

    if bad_everyone:
        score -= 30
        reasons.append(f"@everyone 역할에 과도한 권한({', '.join(bad_everyone)})이 부여되어 있습니다.")

    # 3. 관리자 권한 가진 역할 개수/유저 수
    admin_roles = [r for r in guild.roles if r.permissions.administrator]
    if len(admin_roles) > 5:
        score -= 15
        reasons.append("관리자 권한 역할이 5개를 초과합니다.")
    elif len(admin_roles) > 2:
        score -= 5
        reasons.append("관리자 권한 역할이 다소 많습니다.")

    admin_members = [
        m for m in guild.members
        if not m.bot and (m.guild_permissions.administrator)
    ]
    if len(admin_members) > 10:
        score -= 15
        reasons.append("관리자 권한을 가진 유저가 10명을 초과합니다.")
    elif len(admin_members) > 5:
        score -= 5
        reasons.append("관리자 권한을 가진 유저가 다소 많습니다.")

    # 4. 봇 수/비율
    human_count = len([m for m in guild.members if not m.bot])
    bot_count = len([m for m in guild.members if m.bot])
    if human_count > 0:
        bot_ratio = bot_count / (human_count + bot_count)
        if bot_ratio > 0.5:
            score -= 10
            reasons.append("봇 비율이 50%를 초과합니다. 권한 관리에 주의가 필요합니다.")

    # 5. 최소/최대 클램핑
    if score < 0:
        score = 0
    if score > 100:
        score = 100

    return score, reasons

def send_log_to_web(guild_id: int, user_id: int, action: str, detail: str):
    try:
        resp = requests.post(
            "https://web-api-production-69fc.up.railway.app/api/log",
            json={
                "guild_id": guild_id,
                "user_id": user_id,
                "action": action,
                "detail": detail,
            },
            timeout=5,
        )
        print("[WEB_LOG]", resp.status_code, resp.text)
    except Exception as e:
        print("[WEB_LOG_ERROR]", repr(e))


class VerifyView(discord.ui.View):
    def __init__(
        self,
        code: str,
        expiretime: datetime,
        guildid: int,
        roblox_nick: str,
        roblox_user_id: int,
    ):
        super().__init__(timeout=300)
        self.code = code
        self.expiretime = expiretime
        self.guildid = guildid
        self.roblox_nick = roblox_nick
        self.roblox_user_id = roblox_user_id

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.green)
    async def verifybutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction is None:
            return

        try:
            guild: Optional[discord.Guild] = interaction.guild or bot.get_guild(self.guildid)
            if guild is None:
                print(
                    f"[WEB_LOG_ERROR_VERIFY_BUTTON] guild is None, "
                    f"user={interaction.user} guild_id={self.guildid}"
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "길드를 찾을 수 없습니다. 서버에서 다시 /인증 해 주세요.",
                        ephemeral=True,
                    )
                return
            if datetime.now() > self.expiretime:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "인증 코드가 만료되었습니다. 다시 /인증 명령을 사용해 주세요.",
                        ephemeral=True,
                    )
                return
            description = await roblox_get_description_by_user_id(self.roblox_user_id)
            if description is None:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Roblox 프로필 설명을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.",
                        ephemeral=True,
                    )
                return

            if self.code not in description:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Roblox 프로필 설명에 인증 코드가 없습니다. 설명에 코드를 넣고 다시 시도해 주세요.",
                        ephemeral=True,
                    )
                return
            config_role_id = get_guild_role_id(guild.id)

            KST = timezone(timedelta(hours=9))
            now_kst = datetime.now(KST)

            member = guild.get_member(interaction.user.id)
            if member is None:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "서버에서 회원 정보를 찾을 수 없습니다.",
                        ephemeral=True,
                    )
                return

            verify_role = guild.get_role(VERIFY_ROLE_ID)
            unverify_role = guild.get_role(UNVERIFY_ROLE_ID)
            log_channel = guild.get_channel(ADMIN_LOG_CHANNEL_ID)

            if verify_role is None:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "인증 역할을 찾을 수 없습니다. 관리자에게 문의해 주세요.",
                        ephemeral=True,
                    )
                return
            if verify_role in member.roles:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "이미 인증된 상태입니다.",
                        ephemeral=True,
                    )
                return

            account_created = member.created_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")
            if unverify_role and unverify_role in member.roles:
                await member.remove_roles(unverify_role)

                if log_channel:
                    embed_remove = discord.Embed(
                        title="🔴 역할 제거",
                        color=discord.Color.red(),
                        timestamp=now_kst
                    )

                    if guild.icon:
                        embed_remove.set_thumbnail(url=guild.icon.url)

                    embed_remove.add_field(
                        name="디스코드",
                        value=(
                            f"{member.mention}\n"
                            f"{member.name}\n"
                            f"ID: {member.id}\n"
                            f"계정 생성일: {account_created}"
                        ),
                        inline=False
                    )

                    embed_remove.add_field(
                        name="로블록스",
                        value=f"{self.roblox_nick}",
                        inline=False
                    )

                    embed_remove.add_field(
                        name="역할",
                        value=f"{unverify_role.mention}",
                        inline=False
                    )

                    embed_remove.add_field(
                        name="실행자",
                        value=f"{interaction.user.mention}",
                        inline=False
                    )

                    embed_remove.set_footer(text="Made by Lunar | KST(UTC+9)")

                    await log_channel.send(embed=embed_remove)
            await member.add_roles(verify_role)

            if log_channel:
                embed_add = discord.Embed(
                    title="🟢 역할 추가",
                    color=discord.Color.green(),
                    timestamp=now_kst
                )

                if guild.icon:
                    embed_add.set_thumbnail(url=guild.icon.url)

                embed_add.add_field(
                    name="디스코드",
                    value=(
                        f"{member.mention}\n"
                        f"{member.name}\n"
                        f"ID: {member.id}\n"
                        f"계정 생성일: {account_created}"
                    ),
                    inline=False
                )

                embed_add.add_field(
                    name="로블록스",
                    value=f"{self.roblox_nick}",
                    inline=False
                )

                embed_add.add_field(
                    name="역할",
                    value=f"{verify_role.mention}",
                    inline=False
                )

                embed_add.add_field(
                    name="실행자",
                    value=f"{interaction.user.mention}",
                    inline=False
                )

                embed_add.set_footer(text="Made by Lunar | KST(UTC+9)")

                await log_channel.send(embed=embed_add)
            try:
                save_verification_log(member.name, self.roblox_nick)
            except Exception as e:
                print("[VERIFY_LOG_ERROR]", e)
            send_log_to_web(
                guild_id=guild.id,
                user_id=interaction.user.id,
                action="verify_success",
                detail=f"{self.roblox_nick} ({self.roblox_user_id})",
            )
            try:
                log_ch_id = get_log_channel(guild.id, "verify")
                if log_ch_id:
                    log_ch = guild.get_channel(log_ch_id) or await guild.fetch_channel(log_ch_id)
                    if log_ch:
                        success_embed = make_verify_embed(
                            VerifyLogType.SUCCESS,
                            user=member,
                            roblox_nick=self.roblox_nick,
                            group_rank=None,
                            account_age_days=None,
                            new_nick=member.nick,
                            at_time=datetime.now(),
                        )
                        await log_ch.send(embed=success_embed)
            except Exception as e:
                print("[VERIFY_SUCCESS_LOG_ERROR]", repr(e))
            if not interaction.response.is_done():
                await interaction.response.send_message("인증이 완료되었습니다!", ephemeral=True)

        except Exception as e:
            add_error_log(f"verifybutton: {repr(e)}")
            print("[WEB_LOG_ERROR_VERIFY_BUTTON]", repr(e))
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "인증 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
                    ephemeral=True,
                )
                
class EmbedModal(Modal, title="엠베드 생성"):

    title_input = TextInput(label="제목", required=False)
    desc_input = TextInput(label="내용", style=discord.TextStyle.paragraph, required=False)
    color_input = TextInput(label="색상 (#ff0000)", required=False)
    image_input = TextInput(label="이미지 URL", required=False)
    footer_input = TextInput(label="푸터", required=False)

    async def on_submit(self, interaction: discord.Interaction):

        color = self.color_input.value or "#5865F2"

        try:
            color = int(color.replace("#", ""), 16)
        except:
            color = 0x5865F2

        embed = discord.Embed(
            title=self.title_input.value or None,
            description=self.desc_input.value or None,
            color=color
        )

        if self.image_input.value:
            embed.set_image(url=self.image_input.value)

        if self.footer_input.value:
            embed.set_footer(text=self.footer_input.value)

        await interaction.response.send_message(embed=embed)

class VerifyLogType(str, Enum):
    REQUEST = "request"
    SUCCESS = "success"
    NO_GROUP = "no_group"
    INVALID_NICK = "invalid_nick" 

class RankLogType(str, Enum):
    PROMOTE = "promote"
    DEMOTE = "demote" 

class RankSummaryType(str, Enum):
    BULK_PROMOTE = "bulk_promote"
    BULK_DEMOTE = "bulk_demote"

class PatchModal(discord.ui.Modal, title="패치 공지"):

    title_input = discord.ui.TextInput(
        label="패치 제목",
        max_length=100
    )

    content_input = discord.ui.TextInput(
        label="패치 내용",
        style=discord.TextStyle.paragraph,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):

        version = increase_version()

        embed = discord.Embed(
            title=f"📢 패치 공지 - Ver. {version}",
            description=f"**{self.title_input.value}**\n\n{self.content_input.value}",
            color=0x00ffcc
        )

        await interaction.channel.send(embed=embed)

        await interaction.response.send_message(
            f"패치 공지 완료\n버전 : {version}",
            ephemeral=True
        )

class ShopView(View):
    def __init__(self, guild: discord.Guild, items: list[tuple]):
        super().__init__(timeout=60)
        self.guild = guild
        self.items = items   [(name, price, type, role_id, level, exp), ...]
        self.index = 0
        self.per_page = 10

    def make_page_embed(self) -> discord.Embed:
        start = self.index * self.per_page
        end = start + self.per_page
        chunk = self.items[start:end]

        lines = []
        for name, price, itype, role_id, level_val, exp_val in chunk:
            extra = ""
            if itype == "role" and role_id:
                role = self.guild.get_role(role_id)
                if role:
                    extra = f" → 역할: {role.mention}"
            elif itype == "level" and level_val is not None:
                extra = f" → 레벨 +{level_val}"
            elif itype == "exp" and exp_val is not None:
                extra = f" → 경험치 +{exp_val}"

            lines.append(f"• `{name}` | 가격: `{price}` | 타입: `{itype}`{extra}")

        desc = "\n".join(lines) if lines else "이 페이지에는 아이템이 없습니다."

        embed = discord.Embed(
            title=f"🛒 아이템 상점 (페이지 {self.index+1}/{self.max_page})",
            description=desc,
            color=discord.Color.blurple(),
        )
        return embed

    @property
    def max_page(self) -> int:
        return max(1, (len(self.items) + self.per_page - 1) // self.per_page)

    async def update(self, interaction: discord.Interaction):
        embed = self.make_page_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="⬅ 이전", style=ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
        await self.update(interaction)

    @button(label="다음 ➡", style=ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button):
        if self.index < self.max_page - 1:
            self.index += 1
        await self.update(interaction)

def make_verify_embed(
    log_type: VerifyLogType,
    *,
    user: discord.abc.User | discord.Member | None = None,
    roblox_nick: str | None = None,
    group_rank: str | None = None,
    account_age_days: int | None = None,
    code: str | None = None,
    new_nick: str | None = None,
    group_id: int | None = None,
    input_nick: str | None = None,
    fail_reason: str | None = None,
    at_time: datetime | None = None,
) -> discord.Embed:
    at_time = at_time or datetime.now() 

    if log_type is VerifyLogType.REQUEST:
        embed = discord.Embed(
            title="✅ 인증 요청",
            color=discord.Color.blurple(),
            description="새로운 인증 코드 발급",
        )
        if user:
            embed.add_field(name="유저", value=user.mention, inline=False)
        if roblox_nick:
            embed.add_field(name="로블록스", value=f"`{roblox_nick}`", inline=True)
        if group_rank:
            embed.add_field(name="그룹 랭크", value=group_rank, inline=True)
        if account_age_days is not None:
            embed.add_field(name="계정 나이", value=f"{account_age_days}일", inline=True)
        if code:
            embed.add_field(name="인증 코드", value=f"`{code}`", inline=True) 

    elif log_type is VerifyLogType.SUCCESS:
        embed = discord.Embed(
            title="<:verfired_green:1479810239619530752> 인증 성공",
            color=discord.Color.green(),
            description="새로운 유저가 인증을 완료했습니다.",
        )
        if user:
            embed.add_field(name="유저", value=user.mention, inline=False)
        if roblox_nick:
            embed.add_field(name="로블록스", value=f"`{roblox_nick}`", inline=True)
        if group_rank:
            embed.add_field(name="그룹 랭크", value=group_rank, inline=True)
        if account_age_days is not None:
            embed.add_field(name="계정 나이", value=f"{account_age_days}일", inline=True)
        if new_nick:
            embed.add_field(name="새 닉네임", value=f"`{new_nick}`", inline=False)
        embed.add_field(
            name="인증 시각",
            value=at_time.strftime("%Y년 %m월 %d일 %A %p %I:%M"),
            inline=False,
        ) 

    elif log_type is VerifyLogType.NO_GROUP:
        embed = discord.Embed(
            title="<:_red:1479810110632099972> 그룹 미가입",
            color=discord.Color.orange(),
            description="그룹 미가입 상태로 인증 실패",
        )
        if user:
            embed.add_field(name="유저", value=user.mention, inline=False)
        if roblox_nick:
            embed.add_field(name="로블록스", value=f"`{roblox_nick}`", inline=True)
        if group_id is not None:
            embed.add_field(name="그룹 ID", value=str(group_id), inline=True) 

    elif log_type is VerifyLogType.INVALID_NICK:
        embed = discord.Embed(
            title="<:_red:1479810110632099972> 인증 실패",
            color=discord.Color.red(),
            description="존재하지 않는 로블록스 닉네임",
        )
        if user:
            embed.add_field(name="유저", value=user.mention, inline=False)
        if input_nick:
            embed.add_field(name="입력한 닉네임", value=f"`{input_nick}`", inline=True)
        embed.add_field(
            name="실패 사유",
            value=fail_reason or "사용자를 찾을 수 없음",
            inline=False,
        )
    else:
        embed = discord.Embed(title="알 수 없는 로그 타입", color=discord.Color.dark_grey()) 

    embed.set_footer(text="Made By Lunar")
    return embed 

def make_rank_log_embed(
    log_type: RankLogType,
    *,
    target_name: str,
    old_rank: str,
    new_rank: str,
    executor: discord.abc.User | discord.Member | None = None,
) -> discord.Embed:
    if log_type is RankLogType.DEMOTE:
        title = "⬇️ 강등"
        desc = "멤버가 강등되었습니다."
        color = discord.Color.red()
    else:
        title = "⬆️ 승진"
        desc = "멤버가 승진되었습니다."
        color = discord.Color.green() 

    embed = discord.Embed(title=title, description=desc, color=color) 

    embed.add_field(name="대상", value=f"`{target_name}`", inline=False)
    embed.add_field(name="이전 랭크", value=old_rank, inline=True)
    embed.add_field(name="새 랭크", value=new_rank, inline=True) 

    if executor:
        embed.add_field(name="실행자", value=executor.mention, inline=False) 

    embed.set_footer(text="Made By Lunar")
    return embed 

def make_bulk_rank_summary_embed(
    summary_type: RankSummaryType,
    *,
    role_name: str,
    total: int,
    success: int,
    failed: int,
    executor: discord.abc.User | discord.Member | None = None,
) -> discord.Embed:
    if summary_type is RankSummaryType.BULK_PROMOTE:
        title = "<:Chack_blue:1479810189434683402> 일괄 승진 완료"
        color = discord.Color.green()
        desc = "여러 멤버 승진 작업이 완료되었습니다."
    else:
        title = "<:Chack_blue:1479810189434683402> 일괄 강등 완료"
        color = discord.Color.red()
        desc = "여러 멤버 강등 작업이 완료되었습니다." 

    embed = discord.Embed(title=title, description=desc, color=color)
    embed.add_field(name="변경 역할", value=f"`{role_name}`", inline=False)
    embed.add_field(name="총 처리", value=f"{total}명", inline=True)
    embed.add_field(name="<:Chack_blue:1479810189434683402> 성공", value=f"{success}명", inline=True)
    embed.add_field(name="<:X_red:1479810084900044851> 실패", value=f"{failed}명", inline=True) 

    if executor:
        embed.add_field(name="실행자", value=executor.mention, inline=False) 

    embed.set_footer(text="Made By Lunar")
    return embed

@bot.tree.command(
    name="community_view",
    description="커뮤니티 글을 조회합니다."
)
@app_commands.describe(
    title="검색할 제목 (비우면 최신 목록)",
    page="페이지 (기본 1)"
)
async def community_view(
    interaction: discord.Interaction,
    title: str | None = None,
    page: int = 1
):
    guild = interaction.guild
    guild_id = guild.id if guild else 0
    per_page = 5
    offset = (page - 1) * per_page

    if title:
        query = """
            SELECT id, author_id, title, content, created_at
            FROM community_posts
            WHERE guild_id=? AND title LIKE ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """
        params = (guild_id, f"%{title}%", per_page, offset)
    else:
        query = """
            SELECT id, author_id, title, content, created_at
            FROM community_posts
            WHERE guild_id=?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """
        params = (guild_id, per_page, offset)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        msg = "해당 제목의 글이 없습니다." if title else "표시할 커뮤니티 글이 없습니다."
        await interaction.response.send_message(msg, ephemeral=True)
        return

    embeds: list[discord.Embed] = []
    for pid, author_id, t, content, created_at in rows:
        e = discord.Embed(
            title=f"#{pid} | {t}",
            description=content[:2000],
            color=discord.Color.green(),
        )
        author = guild.get_member(author_id) if guild else None
        if author:
            e.set_author(name=author.display_name, icon_url=author.display_avatar.url)
        e.set_footer(text=created_at)
        embeds.append(e)

    header = (
        f"검색어: `{title}` (페이지 {page})"
        if title else
        f"최신 커뮤니티 글 (페이지 {page})"
    )

    await interaction.response.send_message(
        content=header,
        embeds=embeds,
        ephemeral=True,
    )

@bot.tree.command(
    name="커뮤니티_작성",
    description="커뮤니티 양식을 모달로 제출합니다.",
    )
async def community_create(interaction: discord.Interaction):
    modal = CommunityFormModal()
    await interaction.response.send_modal(modal)
    
@bot.tree.command(
    name="커뮤니티_조회",
    description="커뮤니티 글을 조회합니다."
)

@app_commands.describe(
    title="검색할 제목",
    page="페이지 (기본 1)"
)
async def community_work(
    interaction: discord.Interaction,
    title: str,
    page: int = 1
):
    guild = interaction.guild
    guild_id = guild.id if guild else 0
    per_page = 5
    offset = (page - 1) * per_page

    cursor.execute(
        """
        SELECT id, author_id, title, content, created_at
        FROM community_posts
        WHERE guild_id=? AND title LIKE ?
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (guild_id, f"%{title}%", per_page, offset),
    )
    rows = cursor.fetchall()
    if not rows:
        await interaction.response.send_message("해당 제목의 글이 없습니다.", ephemeral=True)
        return

    embeds = []
    for pid, author_id, t, content, created_at in rows:
        e = discord.Embed(
            title=f"#{pid} | {t}",
            description=content[:2000],
            color=discord.Color.green(),
        )
        author = guild.get_member(author_id) if guild else None
        if author:
            e.set_author(name=author.display_name, icon_url=author.display_avatar.url)
        e.set_footer(text=created_at)
        embeds.append(e)

    await interaction.response.send_message(
        content=f"검색어: `{title}` (페이지 {page})",
        embeds=embeds,
        ephemeral=True,
    )

@bot.tree.command(
    name="커뮤니티_삭제",
    description="커뮤니티 글을 삭제.",
)
@app_commands.describe(
    post_id="삭제할 글 번호",
    reason="삭제 사유 (선택)"
)
async def community_delete(
    interaction: discord.Interaction,
    post_id: int,
    reason: str | None = None,
):
    guild = interaction.guild
    guild_id = guild.id if guild else 0
    user = interaction.user

    # 글 정보 가져오기
    cursor.execute(
        "SELECT title, author_id, content FROM community_posts WHERE guild_id=? AND id=?",
        (guild_id, post_id),
    )
    row = cursor.fetchone()
    if not row:
        await interaction.response.send_message("해당 번호의 글이 없습니다.", ephemeral=True)
        return

    title, author_id, content = row
    is_admin_user = is_admin(user)

    # 권한 체크: 작성자 또는 관리자만 허용
    if (author_id != user.id) and (not is_admin_user):
        await interaction.response.send_message(
            "본인이 작성한 글만 삭제할 수 있습니다.",
            ephemeral=True,
        )
        return

    # 삭제
    cursor.execute(
        "DELETE FROM community_posts WHERE guild_id=? AND id=?",
        (guild_id, post_id),
    )
    conn.commit()

    # 작성자에게 DM 알림
    try:
        author_user = await bot.fetch_user(author_id)
        if author_user:
            dm_embed = discord.Embed(
                title="커뮤니티 글이 삭제되었습니다",
                description=(
                    f"서버: **{guild.name if guild else '알 수 없음'}**\n"
                    f"글 번호: `#{post_id}`\n"
                    f"제목: **{title}**"
                ),
                color=discord.Color.red(),
            )
            preview = (content[:200] + "…") if len(content) > 200 else content
            if preview:
                dm_embed.add_field(name="내용 미리보기", value=preview, inline=False)
            if reason:
                dm_embed.add_field(name="삭제 사유", value=reason, inline=False)

            dm_embed.set_footer(
                text=f"삭제자: {user} ({user.id})"
            )
            await author_user.send(embed=dm_embed)
    except discord.Forbidden:
        pass
    except Exception as e:
        print(f"community_delete DM error: {e}")

    # 실행자 피드백
    if is_admin_user and author_id != user.id:
        msg = f"#{post_id} `{title}` 글을 삭제했습니다. (작성자: <@{author_id}>)"
    else:
        msg = f"본인이 작성한 글 #{post_id} `{title}` 을(를) 삭제했습니다."

    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="인증", description="로블록스 계정 인증을 시작합니다.")
@app_commands.describe(로블닉="로블록스 닉네임")
async def verify(interaction: discord.Interaction, 로블닉: str):
    await interaction.response.defer(ephemeral=True)


    print(
        f"/인증 로블닉:{로블닉} "
        f"(user={interaction.user} id={interaction.user.id})"
    )

    if is_already_verified(interaction.guild.id, interaction.user.id):
        await interaction.followup.send(
            "이미 인증된 사용자입니다. (웹 로그 기준)",
            ephemeral=True,
        )
        return

    user_id = await roblox_get_user_id_by_username(로블닉)
    if not user_id:
        await interaction.followup.send(
            "해당 닉네임의 로블록스 계정을 찾을 수 없습니다.",
            ephemeral=True,
        )
        return
    

    cursor.execute(
        "SELECT group_id FROM blacklist WHERE guild_id=?",
        (interaction.guild.id,),
    )
    blacklist_groups = {row[0] for row in cursor.fetchall()}
    if blacklist_groups:
        

        user_groups = await roblox_get_user_groups(user_id)
        blocked_groups = [g for g in user_groups if g in blacklist_groups]
        if blocked_groups:
            await interaction.followup.send(
                "❌ 블랙리스트된 그룹에 속해 있어서 인증할 수 없습니다.\n"
                f"차단된 그룹: {', '.join(map(str, blocked_groups))}",
                ephemeral=True,
            )
            return

    code = generate_code()
    expire_time = datetime.now() + timedelta(minutes=5)
    dm_embed = discord.Embed(
        title="로블록스 인증",
        color=discord.Color.blue(),
    )
    dm_embed.description = (
        f"> Roblox: `{로블닉}` (ID: `{user_id}`)\n"
        f"> 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "1️⃣ Roblox 프로필로 이동\n"
        "2️⃣ 설명란에 코드 입력\n"
        "3️⃣ '인증하기' 버튼 클릭\n\n"
        f"🔐 코드: `{code}`\n"
        "⏱ 남은 시간: 5분\n\n"
        "Made by Lunar"
    )

    view = VerifyView(
        code=code,
        expiretime=expire_time,
        guildid=interaction.guild.id,
        roblox_nick=로블닉,
        roblox_user_id=user_id,
    )
    try:
        log_ch_id = get_log_channel(interaction.guild.id, "verify")
        if log_ch_id:
            log_ch = interaction.guild.get_channel(log_ch_id) or await interaction.guild.fetch_channel(log_ch_id)
            if log_ch:
                req_embed = make_verify_embed(
                    VerifyLogType.REQUEST,
                    user=interaction.user,
                    roblox_nick=로블닉,
                    code=code,
                )
                await log_ch.send(embed=req_embed)
    except Exception as e:
        print("[VERIFY_REQUEST_LOG_ERROR]", repr(e))
    try:
        await interaction.user.send(embed=dm_embed, view=view)
        await interaction.followup.send("📩 DM을 확인해주세요.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(
            "DM 전송에 실패했습니다. DM 수신을 허용하고 다시 시도해주세요.",
            ephemeral=True,
        )

@bot.tree.command(name="일괄강제인증", description="현재 서버의 모든 미인증자를 강제인증 처리합니다. (제작자 전용)")
async def bulk_force_verify(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("길드에서만 사용 가능합니다.", ephemeral=True)
        return
    if not is_owner(interaction.user):
        await interaction.response.send_message("제작자만 사용할 수 있습니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    log_channel_id = get_log_channel(guild.id, "verify")
    log_channel: discord.TextChannel | None = guild.get_channel(log_channel_id) if log_channel_id else None
    members: list[discord.Member] = [m for m in guild.members if not m.bot]
    verified_ids: set[int] = set()
    loop = asyncio.get_running_loop()

    def _check_one(user_id: int) -> bool:
        return is_already_verified(guild.id, user_id)

    async def check_verified(m: discord.Member):
        is_verified = await loop.run_in_executor(None, _check_one, m.id)
        if is_verified:
            verified_ids.add(m.id)

    await asyncio.gather(*(check_verified(m) for m in members))

    targets = [m for m in members if m.id not in verified_ids]

    total = len(targets)
    success = 0
    fail = 0
    if log_channel:
        embed = discord.Embed(
            title="<:Chack_blue:1479810189434683402> 일괄 강제인증 시작",
            description=f"대상 인원: {total}명",
            color=discord.Color.orange()
        )
        embed.add_field(name="<:Chack_blue:1479810189434683402> 성공", value=str(success))
        embed.add_field(name="<:X_red:1479810084900044851> 실패", value=str(fail))
        embed.set_footer(text=f"요청자: {interaction.user} ({interaction.user.id})")
        progress_msg = await log_channel.send(embed=embed)
    else:
        progress_msg = None

    for idx, member in enumerate(targets, start=1):
        try:
            verify_role = guild.get_role(VERIFY_ROLE_ID)
            unverify_role = guild.get_role(UNVERIFY_ROLE_ID)

            if verify_role and verify_role in member.roles:
                continue

            cursor.execute(
                """
                INSERT OR REPLACE INTO forced_verified(discord_id, guild_id, roblox_nick, roblox_user_id, rank_role)
                VALUES(?, ?, ?, ?, ?)
                """,
                (member.id, guild.id, None, None, "forced")
            )
            conn.commit()

            if verify_role:
                await member.add_roles(verify_role, reason="일괄 강제인증")
            if unverify_role and unverify_role in member.roles:
                await member.remove_roles(unverify_role, reason="일괄 강제인증")

            send_log_to_web(
                guild_id=guild.id,
                user_id=member.id,
                action="force_verify_bulk",
                detail=f"일괄 강제인증 처리 (요청자: {interaction.user.id})"
            )

            success += 1

        except Exception as e:
            fail += 1
            add_error_log(f"bulk_force_verify: {repr(e)}")
        if idx % 20 == 0:
            await asyncio.sleep(0)

        if progress_msg and (idx % 10 == 0 or idx == total):
            progress_embed = discord.Embed(
                title="일괄 강제인증 진행 중",
                description=f"{idx}/{total}명 처리 완료",
                color=discord.Color.blurple()
            )
            progress_embed.add_field(name="성공", value=str(success))
            progress_embed.add_field(name="실패", value=str(fail))
            progress_embed.set_footer(text=f"요청자: {interaction.user} ({interaction.user.id})")
            try:
                await progress_msg.edit(embed=progress_embed)
            except discord.NotFound:
                progress_msg = None
    cursor.execute(
        """
        INSERT INTO stats(guild_id, verify_count, force_count, cancel_count)
        VALUES(?, 0, ?, 0)
        ON CONFLICT(guild_id) DO UPDATE SET force_count = stats.force_count + ?
        """,
        (guild.id, success, success)
    )
    conn.commit()

    result_text = (
        f"대상: {total}명\n"
        f"<:Chack_blue:1479810189434683402> 성공: {success}명\n"
        f"<:X_red:1479810084900044851>  실패: {fail}명"
    )
    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(content=result_text)
        else:
            await interaction.response.send_message(result_text)
    except discord.NotFound:
        pass

    if log_channel:
        final_embed = discord.Embed(
            title="<:Chack_blue:1479810189434683402> 일괄 강제인증 완료",
            description=result_text,
            color=discord.Color.green()
        )
        final_embed.set_footer(text=f"요청자: {interaction.user} ({interaction.user.id})")
        await log_channel.send(embed=final_embed)

@bot.tree.command(name="돈추가", description="유저에게 돈을 추가합니다. (관리자)")
@app_commands.describe(
    유저="돈을 받을 유저",
    금액="추가할 금액"
)
async def add_money(
    interaction: discord.Interaction,
    유저: discord.Member,
    금액: int
):

    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    if 금액 <= 0:
        await interaction.response.send_message("금액은 1 이상이어야 합니다.", ephemeral=True)
        return
    user = get_user(유저.id)

    cur.execute(
        "UPDATE economy SET money = money + ? WHERE user_id=?",
        (금액, 유저.id)
    )
    conn.commit()

    await interaction.response.send_message(
        f"💰 {유저.mention}에게 `{금액}`원을 추가했습니다."
    )

@bot.tree.command(name="강제인증해제", description="특정 유저의 강제인증을 해제합니다. (관리자)")
@app_commands.describe(
    user="강제인증을 해제할 디스코드 유저"
)
async def force_unverify(
    interaction: discord.Interaction,
    user: discord.User,
):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("길드에서만 사용할 수 있습니다.", ephemeral=True)
        return

    member = guild.get_member(user.id)
    if member is None:
        await interaction.followup.send("해당 유저를 서버에서 찾을 수 없습니다.", ephemeral=True)
        return

    verify_role = guild.get_role(VERIFY_ROLE_ID)
    unverify_role = guild.get_role(UNVERIFY_ROLE_ID)
    cursor.execute(
        "DELETE FROM forced_verified WHERE discord_id = ? AND guild_id = ?",
        (member.id, guild.id),
    )
    conn.commit()
    try:
        if verify_role and verify_role in member.roles:
            await member.remove_roles(verify_role, reason="강제인증 해제")
        if unverify_role and unverify_role not in member.roles:
            await member.add_roles(unverify_role, reason="강제인증 해제")
    except Exception as e:
        add_error_log(f"force_unverify_roles: {repr(e)}")
        await interaction.followup.send(f"역할 변경 중 오류 발생: {e}", ephemeral=True)
        return
    send_log_to_web(
        guild_id=guild.id,
        user_id=member.id,
        action="force_unverify",
        detail=f"강제인증 해제 (요청자: {interaction.user.id})",
    )
    cursor.execute(
        """
        INSERT INTO stats(guild_id, verify_count, force_count, cancel_count)
        VALUES(?, 0, 0, 1)
        ON CONFLICT(guild_id) DO UPDATE SET cancel_count = stats.cancel_count + 1
        """,
        (guild.id,),
    )
    conn.commit()

    await interaction.followup.send(
        f"{member.mention} 님의 강제인증을 해제했습니다.",
        ephemeral=True,
    )
    force_log_ch_id = get_log_channel(guild.id, "force_verify")
    if force_log_ch_id:
        force_log_ch = guild.get_channel(force_log_ch_id) or await guild.fetch_channel(force_log_ch_id)
        if force_log_ch:
            embed = discord.Embed(
                title="<:_red:1479810110632099972> 강제인증 해제",
                color=discord.Color.red(),
                description="관리자가 강제인증을 해제했습니다.",
            )
            embed.add_field(
                name="대상 유저",
                value=f"{member.mention} (`{member.id}`)",
                inline=False,
            )
            embed.add_field(
                name="실행자",
                value=f"{interaction.user.mention} (`{interaction.user.id}`)",
                inline=False,
            )
            embed.set_footer(text="강제인증 로그")
            await force_log_ch.send(embed=embed)
    if guild:
        await send_admin_log(
            guild,
            title="🔴 강제인증 해제",
            description="관리자가 강제인증을 해제했습니다.",
            color=discord.Color.red(),
            fields=[
                ("대상 유저", f"{member.mention} (`{member.id}`)", False),
                ("실행자", f"{interaction.user.mention} (`{interaction.user.id}`)", False),
            ],
        )

@bot.tree.command(name="강제인증", description="유저를 강제로 인증 처리합니다. (관리자)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.describe(
    user="Discord 유저 멘션",
    roblox_nick="Roblox 닉네임"
)
async def force_verify(interaction: discord.Interaction, user: discord.User, roblox_nick: str):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return 

    await interaction.response.defer(ephemeral=True)
    
    user_id = await roblox_get_user_id_by_username(roblox_nick)
    if not user_id:
        await interaction.followup.send(
            f"해당 닉네임의 로블록스 계정을 찾을 수 없습니다.",
            ephemeral=True,
        )
        return
    cursor.execute(
        """INSERT OR REPLACE INTO users(discord_id, guild_id, roblox_nick, roblox_user_id, code, expire_time, verified)
           VALUES(?, ?, ?, ?, ?, ?, 1)""",
        (user.id, interaction.guild.id, roblox_nick, user_id, "forced", datetime.now().isoformat()),
    )
    conn.commit() 
    try:
        save_verification_log(user.name, roblox_nick)
    except:
        pass 
    role_id = get_guild_role_id(interaction.guild.id)
    member = interaction.guild.get_member(user.id)
    
    if role_id and member:
        role = interaction.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role)
            except:
                pass 
    try:
        resp = requests.post(
            f"{RANK_API_URL_ROOT}/bulk-status",
            json={"usernames": [roblox_nick]},
            headers=_rank_api_headers(),
            timeout=15,
        )
        
        rank_name = "?"
        rank_num = 0
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results and results[0].get("success"):
                role_info = results[0].get("role", {})
                rank_name = role_info.get("name", "?")
                rank_num = role_info.get("rank", 0)

        is_junior, is_senior = check_is_officer(rank_num, rank_name)
        
        officer_role_id = get_officer_role_id(interaction.guild.id)
        if officer_role_id and is_junior:
            officer_role = interaction.guild.get_role(officer_role_id)
            if officer_role and member:
                await member.add_roles(officer_role)
        
        senior_officer_role_id = get_senior_officer_role_id(interaction.guild.id)
        if senior_officer_role_id and is_senior:
            senior_officer_role = interaction.guild.get_role(senior_officer_role_id)
            if senior_officer_role and member:
                await member.add_roles(senior_officer_role)
        
    except Exception as e:
        print(f"강제인증 추가 처리 실패: {e}") 

    embed = discord.Embed(
        title="강제인증 완료",
        color=discord.Color.green(),
        description=f"{user.mention} 을(를) {roblox_nick}로 인증 처리했습니다."
    )
    send_log_to_web(
        guild_id=interaction.guild.id,
        user_id=interaction.user.id,
        action="verify_success",
        detail=f"{roblox_nick} ({user_id})",
    ) 

    await interaction.followup.send(embed=embed, ephemeral=True)
    guild = interaction.guild
    if guild:
        await send_admin_log(
            guild,
            title="<:verfired_green:1479810239619530752> 강제인증 실행",
            description="관리자가 유저를 강제인증 처리했습니다.",
            color=discord.Color.green(),
            fields=[
                ("대상 유저", f"{user.mention} (`{user.id}`)", False),
                ("로블록스 닉네임", f"`{roblox_nick}`", False),
                ("실행자", f"{interaction.user.mention} (`{interaction.user.id}`)", False),
            ],
        )

@bot.tree.command(name="버전", description="현재 봇 버전")
async def version_cmd(interaction: discord.Interaction):

    version = get_version()

    await interaction.response.send_message(
        f"현재 버전 : **v{version}**"
    )
    
@bot.tree.command(name="패치공지", description="패치 공지 작성")
async def patch_notice(interaction: discord.Interaction):

    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "관리자만 사용 가능합니다",
            ephemeral=True
        )
        return

    await interaction.response.send_modal(PatchModal())
    
@bot.tree.command(name="채팅그래프")
async def chat_graph(interaction: discord.Interaction):

    cur.execute("""
    SELECT hour, messages
    FROM chat_stats
    ORDER BY hour DESC
    LIMIT 24
    """)

    rows = cur.fetchall()

    if not rows:
        await interaction.response.send_message("데이터 없음")
        return

    rows.reverse()

    hours = [r[0].split(" ")[1] for r in rows]
    counts = [r[1] for r in rows]

    avg = sum(counts) // len(counts)
    peak = max(counts)

    # 📊 그래프 생성
    plt.figure()
    plt.plot(hours, counts)
    plt.xticks(rotation=45)
    plt.title("Chat Activity (24h)")
    plt.xlabel("Time")
    plt.ylabel("Messages")

    # PNG 저장 (메모리)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close()

    file = discord.File(buf, filename="chat_graph.png")

    embed = discord.Embed(
        title="📊 채팅 통계 (최근 24시간)",
        description=f"""
평균 채팅수 : {avg}
피크 채팅수 : {peak}
총 메시지 : {sum(counts)}
"""
    )

    if next_update:
        embed.set_footer(
            text=f"다음 갱신: {next_update.strftime('%H:%M:%S')}"
        )

    await interaction.response.send_message(
        embed=embed,
        file=file
    )

@bot.tree.command(name="공지", description="인증된 모든 유저에게 공지 전송")
@app_commands.describe(
    message="공지 내용",
    color="embed 색상"
)
@app_commands.choices(color=[
    app_commands.Choice(name="파란색", value="blue"),
    app_commands.Choice(name="초록색", value="green"),
    app_commands.Choice(name="빨간색", value="red"),
    app_commands.Choice(name="주황색", value="orange"),
    app_commands.Choice(name="보라색", value="purple"),
    app_commands.Choice(name="금색", value="gold"),
])
async def announce(interaction: discord.Interaction, message: str, color: app_commands.Choice[str] = None):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    colors = {
        "blue": discord.Color.blue(),
        "green": discord.Color.green(),
        "red": discord.Color.red(),
        "orange": discord.Color.orange(),
        "purple": discord.Color.purple(),
        "gold": discord.Color.gold(),
    }
    selected = colors.get(color.value if color else "blue", discord.Color.blue())
    cursor.execute("SELECT DISTINCT discordid FROM users WHERE guildid=? AND verified=1", (guild.id,))
    verified = [r[0] for r in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT discordid FROM forcedverified WHERE guildid=?", (guild.id,))
    forced = [r[0] for r in cursor.fetchall()]
    
    all_users = list(set(verified + forced))
    
    if not all_users:
        await interaction.followup.send("인증된 유저가 없습니다.", ephemeral=True)
        return
    embed = discord.Embed(
        title="📢 공지사항",
        description=message,
        color=selected,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"발신: {interaction.user.name}")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    ch_id = get_log_channel(guild.id, "announce")
    if ch_id:
        ch = guild.get_channel(ch_id) or await guild.fetch_channel(ch_id)
        if ch:
            await ch.send(embed=embed)
    success = fail = 0
    for uid in all_users:
        try:
            u = await bot.fetch_user(uid)
            await u.send(embed=embed)
            success += 1
            await asyncio.sleep(0.3)
        except:
            fail += 1
    
    await interaction.followup.send(
        f"✅ 공지 완료\n• 대상: {len(all_users)}명\n• 성공: {success}명\n• 실패: {fail}명",
        ephemeral=True
    )

@bot.tree.command(name="인증로그보기", description="인증 기록을 확인합니다. (관리자)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.describe(최근="최근 N개 (기본 20)")
async def view_verification_log(interaction: discord.Interaction, 최근: int = 20):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return 

    await interaction.response.defer(ephemeral=True) 

    try:
        resp = requests.get(
            f"{API_BASE}/api/logs/verify",
            params={
                "guild_id": interaction.guild.id,
                "user_id": interaction.user.id,
                "limit": 최근,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            await interaction.followup.send(
                f"웹 로그 조회 실패: {resp.status_code} {resp.text}",
                ephemeral=True,
            )
            return 

        data = resp.json()
        if not data:
            await interaction.followup.send("인증 로그가 없습니다.", ephemeral=True)
            return
        lines = [
            f"{i+1}. [{item['created_at']}] {item['detail']} (user_id={item['user_id']})"
            for i, item in enumerate(data)
        ]
        msg = "\n".join(lines) 

        embed = discord.Embed(
            title="인증 로그 (웹)",
            description=f"```\n{msg[:1900]}\n```",
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"최근 {len(data)}개") 

        await interaction.followup.send(embed=embed, ephemeral=True) 

    except Exception as e:
        await interaction.followup.send(f"로그 읽기 실패: {e}", ephemeral=True) 

@bot.tree.command(name="인증통계", description="서버 인증 통계를 보여줍니다.")
async def verify_stats(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message(
            "길드에서만 사용 가능합니다.",
            ephemeral=True,
        )
        return 

    member = interaction.user
    if not (is_owner(member) or is_admin(member)):
        await interaction.response.send_message(
            "관리자 또는 제작자만 사용할 수 있습니다.",
            ephemeral=True,
        )
        return 

    await interaction.response.defer(ephemeral=True) 
    members: list[discord.Member] = [m for m in guild.members if not m.bot] 
    verified_ids: set[int] = set()
    loop = asyncio.get_running_loop() 

    def _check_one(user_id: int) -> bool:
        return is_already_verified(guild.id, user_id) 

    async def check_verified(m: discord.Member):
        is_verified = await loop.run_in_executor(None, _check_one, m.id)
        if is_verified:
            verified_ids.add(m.id)

    await asyncio.gather(*(check_verified(m) for m in members)) 
    verified_members = [m for m in members if m.id in verified_ids]
    not_verified_members = [m for m in members if m.id not in verified_ids] 

    total_members = len(members)
    verified_count = len(verified_members)
    not_verified_count = len(not_verified_members) 

    verified_pct = round(verified_count / total_members * 100, 2) if total_members else 0
    not_verified_pct = round(not_verified_count / total_members * 100, 2) if total_members else 0 

    def chunk_lines(title: str, members_list: list[discord.Member]):
        chunks = []
        chunk_size = 20
        for i in range(0, len(members_list), chunk_size):
            chunk = members_list[i:i+chunk_size]
            lines = [f"{m.display_name} ({m.id})" for m in chunk]
            chunks.append(f"**{title}**\n" + "\n".join(lines))
        return chunks
       
@bot.tree.command(name="역할목록", description="서버 역할과 봇 역할을 10개씩 출력합니다.(관리자)")
async def role_all(interaction: discord.Interaction): 
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용 가능합니다.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    roles = interaction.guild.roles[::-1]
    roles = [r for r in roles if r.name != "@everyone"]
    
    if roles:
        chunks = [roles[i:i+10] for i in range(0, len(roles), 10)] 

        for idx, chunk in enumerate(chunks, start=1):
            embed = discord.Embed(
                title=f"서버 역할 목록 (총 {len(roles)}개) ({idx}/{len(chunks)})",
                color=discord.Color.blue()
            ) 

            desc = ""
            for role in chunk:
                desc += f"{role.mention} | `{role.id}`\n" 
            embed.description = desc
            await interaction.followup.send(embed=embed, ephemeral=True)
            
    bot_member = interaction.guild.get_member(bot.user.id)
    bot_roles = bot_member.roles[::-1]
    bot_roles = [r for r in bot_roles if r.name != "@everyone"] 

    if bot_roles:
        chunks = [bot_roles[i:i+10] for i in range(0, len(bot_roles), 10)] 

        for idx, chunk in enumerate(chunks, start=1):
            embed = discord.Embed(
                title=f"봇 역할 목록 (총 {len(bot_roles)}개) ({idx}/{len(chunks)})",
                color=discord.Color.green()
            ) 

            desc = ""
            for role in chunk:
                desc += f"{role.mention} | `{role.id}`\n" 

            embed.description = desc
            await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send("봇은 역할이 없습니다.", ephemeral=True)
        
@bot.tree.command(name="전체복구", description="역할, 채널, 카테고리, 유저 역할, 위치까지 한 번에 복구합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def restore_all_command(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    data = load_backup_data(guild.id)
    if not data:
        await interaction.response.send_message("백업 파일이 없습니다.", ephemeral=True)
        return

    roles_data = data.get("roles", [])
    channels_data = data.get("channels", [])
    member_roles_data = data.get("member_roles", {})

    non_category_channels = [
        c for c in sorted(channels_data, key=lambda x: x.get("position", 0))
        if c.get("type") != "category"
    ]
    category_channels = [
        c for c in sorted(channels_data, key=lambda x: x.get("position", 0))
        if c.get("type") == "category"
    ]
    channels_with_category = [
        c for c in non_category_channels if c.get("category")
    ]

    total_steps = (
        len(roles_data)                  # 역할 생성
        + len(non_category_channels)     # 일반 채널 생성
        + len(category_channels)         # 카테고리 생성
        + len(channels_with_category)    # 카테고리 이동
        + len(guild.members)             # 유저 역할 복구
        + len(roles_data)                # 역할 위치 재정렬
        + len(channels_data)             # 채널 위치 재정렬
    )

    if total_steps <= 0:
        await interaction.response.send_message("복구할 데이터가 없습니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    done_steps = 0
    created_roles = 0
    created_channels = 0
    restored_members = 0

    failed_roles = []
    failed_channels = []
    failed_members = []

    me = guild.me

    def make_progress_bar(current: int, total: int, size: int = 20) -> str:
        if total <= 0:
            return f"{'░' * size} 0%"
        ratio = max(0, min(1, current / total))
        filled = int(ratio * size)
        return f"{'█' * filled}{'░' * (size - filled)} {int(ratio * 100)}%"

    async def update_progress(title: str, detail: str):
        content = (
            f"## {title}\n"
            f"`{make_progress_bar(done_steps, total_steps)}`\n"
            f"진행: **{done_steps}/{total_steps}**\n"
            f"{detail}"
        )
        await interaction.edit_original_response(content=content)

    # 1. 역할 복구
    existing_role_names = {role.name for role in guild.roles}

    for role_data in sorted(roles_data, key=lambda x: x.get("position", 0)):
        role_name = role_data["name"]

        await update_progress("전체 복구 진행 중", f"현재 작업: 역할 복구 - `{role_name}`")

        if role_name not in existing_role_names:
            try:
                await guild.create_role(
                    name=role_name,
                    colour=discord.Colour(role_data.get("color", 0)),
                    hoist=role_data.get("hoist", False),
                    mentionable=role_data.get("mentionable", False),
                    permissions=discord.Permissions(role_data.get("permissions", 0)),
                    reason="백업 기반 역할 복구"
                )
                created_roles += 1
                existing_role_names.add(role_name)
            except Exception as e:
                failed_roles.append(f"{role_name}: {e}")

        done_steps += 1
        await asyncio.sleep(0.2)

    try:
        await guild.fetch_roles()
    except Exception:
        pass

    # 2. 텍스트/음성 채널 먼저 복구
    created_channel_objects = {}
    existing_channel_names = {c.name for c in guild.channels}

    for ch in non_category_channels:
        ch_name = ch["name"]

        await update_progress("전체 복구 진행 중", f"현재 작업: 채널 복구 - `{ch_name}`")

        existing_channel = discord.utils.get(guild.channels, name=ch_name)
        if existing_channel:
            created_channel_objects[ch_name] = existing_channel
        else:
            try:
                new_channel = None

                if ch["type"] == "text":
                    new_channel = await guild.create_text_channel(
                        name=ch_name,
                        category=None,
                        reason="백업 기반 채널 복구"
                    )
                elif ch["type"] == "voice":
                    new_channel = await guild.create_voice_channel(
                        name=ch_name,
                        category=None,
                        reason="백업 기반 채널 복구"
                    )

                if new_channel:
                    created_channel_objects[ch_name] = new_channel
                    existing_channel_names.add(ch_name)
                    created_channels += 1

            except Exception as e:
                failed_channels.append(f"{ch_name}: {e}")

        done_steps += 1
        await asyncio.sleep(0.2)

    # 3. 카테고리 복구
    existing_categories = {c.name: c for c in guild.categories}

    for ch in category_channels:
        cat_name = ch["name"]

        await update_progress("전체 복구 진행 중", f"현재 작업: 카테고리 복구 - `{cat_name}`")

        if cat_name not in existing_categories:
            try:
                category = await guild.create_category(
                    name=cat_name,
                    reason="백업 기반 카테고리 복구"
                )
                existing_categories[cat_name] = category
                created_channels += 1
            except Exception as e:
                failed_channels.append(f"{cat_name}: {e}")

        done_steps += 1
        await asyncio.sleep(0.2)

    # 4. 원래 카테고리로 이동
    for ch in channels_with_category:
        ch_name = ch["name"]
        target_category_name = ch.get("category")

        await update_progress(
            "전체 복구 진행 중",
            f"현재 작업: 카테고리 이동 - `{ch_name}` -> `{target_category_name}`"
        )

        channel_obj = created_channel_objects.get(ch_name)
        category_obj = existing_categories.get(target_category_name)

        if channel_obj and category_obj:
            try:
                await channel_obj.edit(
                    category=category_obj,
                    reason="백업 기반 원래 카테고리로 이동"
                )
            except Exception as e:
                failed_channels.append(f"{ch_name} 이동 실패: {e}")

        done_steps += 1
        await asyncio.sleep(0.2)

    # 5. 유저 역할 복구
    for member in guild.members:
        await update_progress("전체 복구 진행 중", f"현재 작업: 유저 역할 복구 - `{member}`")

        role_names = member_roles_data.get(str(member.id), [])
        roles_to_add = []

        for role_name in role_names:
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                continue
            if role.managed:
                continue
            if role in member.roles:
                continue

            try:
                if me and role < me.top_role:
                    roles_to_add.append(role)
            except Exception:
                continue

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="백업 기반 유저 역할 복구")
                restored_members += 1
            except Exception as e:
                failed_members.append(f"{member}: {e}")

        done_steps += 1
        await asyncio.sleep(0.2)

    # 6. 역할 위치 재정렬
    for role_data in sorted(roles_data, key=lambda x: x.get("position", 0)):
        role_name = role_data["name"]

        await update_progress("전체 복구 진행 중", f"현재 작업: 역할 위치 조정 - `{role_name}`")

        role_obj = discord.utils.get(guild.roles, name=role_name)
        if role_obj:
            try:
                target_position = int(role_data.get("position", role_obj.position))
                await role_obj.edit(
                    position=target_position,
                    reason="백업 기반 역할 위치 복구"
                )
            except Exception as e:
                failed_roles.append(f"{role_name} 위치 조정 실패: {e}")

        done_steps += 1
        await asyncio.sleep(0.2)

    # 7. 채널 위치 재정렬
    for ch in sorted(channels_data, key=lambda x: x.get("position", 0)):
        ch_name = ch.get("name")

        await update_progress("전체 복구 진행 중", f"현재 작업: 채널 위치 조정 - `{ch_name}`")

        channel_obj = discord.utils.get(guild.channels, name=ch_name)
        if channel_obj:
            try:
                target_position = int(ch.get("position", channel_obj.position))
                await channel_obj.edit(
                    position=target_position,
                    reason="백업 기반 채널 위치 복구"
                )
            except Exception as e:
                failed_channels.append(f"{ch_name} 위치 조정 실패: {e}")

        done_steps += 1
        await asyncio.sleep(0.2)

    summary = (
        f"역할 생성: **{created_roles}개**\n"
        f"채널/카테고리 생성: **{created_channels}개**\n"
        f"유저 역할 복구: **{restored_members}명**\n"
        f"역할 실패: **{len(failed_roles)}개**\n"
        f"채널 실패: **{len(failed_channels)}개**\n"
        f"유저 실패: **{len(failed_members)}명**"
    )

    if failed_roles:
        summary += "\n\n### 역할 실패 일부\n" + "\n".join(f"- {x}" for x in failed_roles[:10])

    if failed_channels:
        summary += "\n\n### 채널 실패 일부\n" + "\n".join(f"- {x}" for x in failed_channels[:10])

    if failed_members:
        summary += "\n\n### 유저 실패 일부\n" + "\n".join(f"- {x}" for x in failed_members[:10])

    await interaction.edit_original_response(
        content=(
            f"## 전체 복구 완료\n"
            f"`{make_progress_bar(total_steps, total_steps)}`\n"
            f"진행: **{total_steps}/{total_steps}**\n"
            f"{summary}"
        )
    )
    
@bot.tree.command(name="관리자지정", description="관리자 역할 추가/제거 (개발자 전용)")
@app_commands.describe(
    역할="추가할 관리자 역할",
    모드="add = 추가 / remove = 제거 / reset = 전체초기화"
)
@app_commands.choices(
    모드=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="reset", value="reset"),
    ]
)
async def set_admin_roles(
    interaction: discord.Interaction,
    역할: Optional[discord.Role],
    모드: app_commands.Choice[str],
):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message(
            "개발자만 사용할 수 있습니다.", ephemeral=True
        )
        return 

    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "길드에서만 사용할 수 있습니다.", ephemeral=True
        )
        return 

    current_roles = set(get_guild_admin_role_ids(guild.id))

    if 모드.value == "reset":
        set_guild_admin_role_ids(guild.id, [])
        await interaction.response.send_message(
            "관리자 역할을 전부 초기화했습니다.", ephemeral=True
        )
        return 

    if 역할 is None:
        await interaction.response.send_message(
            "역할을 선택해주세요.", ephemeral=True
        )
        return 

    bot_member = guild.me
    if bot_member.top_role <= 역할:
        await interaction.response.send_message(
            "봇보다 높은 역할은 설정할 수 없습니다.", ephemeral=True
        )
        return 

    if 모드.value == "add":
        current_roles.add(역할.id)
        set_guild_admin_role_ids(guild.id, list(current_roles))
        await interaction.response.send_message(
            f"{역할.mention} 을(를) 관리자 역할로 추가했습니다.",
            ephemeral=True
        ) 

    elif 모드.value == "remove":
        if 역할.id in current_roles:
            current_roles.remove(역할.id)
            set_guild_admin_role_ids(guild.id, list(current_roles))
            await interaction.response.send_message(
                f"{역할.mention} 을(를) 관리자 역할에서 제거했습니다.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "해당 역할은 관리자 목록에 없습니다.",
                ephemeral=True
    )
@bot.tree.command(name="명령어로그", description="명령어 사용 기록을 확인합니다. (관리자)")
@app_commands.describe(페이지크기="한 페이지에 표시할 개수 (기본 10)")
async def command_logs(
    interaction: discord.Interaction,
    페이지크기: int = 10,
):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("길드에서만 사용 가능합니다.", ephemeral=True)
        return
    cursor.execute(
        """
        SELECT id, user_name, user_id, command_name, command_full, created_at
        FROM command_logs
        WHERE guild_id=?
        ORDER BY id DESC
        LIMIT 200
        """,
        (guild.id,),
    )
    rows = cursor.fetchall()
    if not rows:
        await interaction.response.send_message("로그가 없습니다.", ephemeral=True)
        return
    lines = []
    for log_id, user_name, user_id, cmd_name, full, created_at in rows:
        lines.append(
            f"{log_id}. [{created_at}] /{cmd_name} - {user_name} ({user_id})\n"
            f"    ⤷ {full}"
        )
    pages: list[str] = []
    for i in range(0, len(lines), 페이지크기):
        chunk = lines[i:i+페이지크기]
        pages.append("\n".join(chunk))

    view = CommandLogView(pages)
    first_embed = discord.Embed(
        title="📜 명령어 로그",
        description=pages[0],
        color=discord.Color.blurple(),
    )
    first_embed.set_footer(text=f"페이지 1/{len(pages)}")

    await interaction.response.send_message(
        embed=first_embed,
        view=view,
        ephemeral=True,
    )
@bot.tree.command(name="명단", description="Roblox 그룹 역할 리스트를 보여줍니다.")
async def list_roles(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return 

    if not RANK_API_URL_ROOT or not RANK_API_KEY:
        await interaction.response.send_message(
            "랭킹 서버 설정이 되어 있지 않습니다.", ephemeral=True
        )
        return 

    await interaction.response.defer(ephemeral=True) 

    try:
        resp = requests.get(
            f"{RANK_API_URL_ROOT}/roles",
            headers=_rank_api_headers(),
            timeout=15,
        )
        if resp.status_code != 200:
            await interaction.followup.send(
                f"역할 목록 불러오기 실패 (HTTP {resp.status_code}): {resp.text}",
                ephemeral=True,
            )
            return 

        roles = resp.json()   [{ name, rank, id }, ...]
        total = len(roles) 

        if not roles:
            await interaction.followup.send("역할이 없습니다.", ephemeral=True)
            return 
        PER_EMBED = 10
        embeds: list[discord.Embed] = [] 

        for i in range(0, total, PER_EMBED):
            chunk = roles[i:i + PER_EMBED] 

            embed = discord.Embed(
                title="Roblox 그룹 역할 리스트",
                description=f"{i + 1} ~ {min(i + PER_EMBED, total)} / {total}개",
                colour=discord.Colour.blurple(),
            )
            embed.set_footer(text=f"총 역할 개수: {total}개") 

            for r in chunk:
                name = r.get("name", "?")
                rank = r.get("rank", "?")
                role_id = r.get("id", "?")
                
                embed.add_field(
                    name=name,
                    value=f"rank: `{rank}` / id: `{role_id}`",
                    inline=False,
                ) 

            embeds.append(embed) 
        await interaction.followup.send(embeds=embeds, ephemeral=True) 

    except Exception as e:
        await interaction.followup.send(
            f"역할 목록 중 에러 발생: {e}",
            ephemeral=True,
        )
        
@bot.tree.command(name="승진", description="Roblox 그룹 랭크를 특정 역할로 변경합니다. (관리자)")
@app_commands.describe(
    username="Roblox 본닉",
    role_name="그룹 역할 이름",
)
async def promote_cmd(
    interaction: discord.Interaction,
    username: str,
    role_name: str,
):
    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "관리자만 사용할 수 있습니다.",
            ephemeral=True
        )
        return

    if not RANK_API_URL_ROOT or not RANK_API_KEY:
        await interaction.response.send_message(
            "랭킹 서버 설정이 되어 있지 않습니다.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        payload = {"username": username, "rank": role_name}

        resp = requests.post(
            f"{RANK_API_URL_ROOT}/rank",
            json=payload,
            headers=_rank_api_headers(),
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()

            new_role = data.get("newRole", {})
            old_role = data.get("oldRole", {})

            old_rank_str = f"{old_role.get('name','?')} (Rank {old_role.get('rank','?')})"
            new_rank_str = f"{new_role.get('name','?')} (Rank {new_role.get('rank','?')})"

            await interaction.followup.send(
                f"`{username}` 님을 역할 `{role_name}` 으로 변경했습니다.\n"
                f"실제 반영: {new_rank_str}",
                ephemeral=True,
            )

            guild = interaction.guild
            if guild:
                log_channel_id = get_log_channel(guild.id, "group_change")

                if log_channel_id:
                    try:
                        log_ch = (
                            guild.get_channel(log_channel_id)
                            or await guild.fetch_channel(log_channel_id)
                        )

                        if log_ch:
                            embed = make_rank_log_embed(
                                RankLogType.PROMOTE,
                                target_name=username,
                                old_rank=old_rank_str,
                                new_rank=new_rank_str,
                                executor=interaction.user,
                            )

                            await log_ch.send(embed=embed)

                    except Exception as e:
                        print("[RANK_PROMOTE_LOG_ERROR]", repr(e))

        else:
            await interaction.followup.send(
                f"승진 실패 (HTTP {resp.status_code}): {resp.text}",
                ephemeral=True,
            )

    except Exception as e:
        await interaction.followup.send(
            f"요청 중 에러 발생: {e}",
            ephemeral=True,
        )

@bot.tree.command(name="강등", description="Roblox 그룹 랭크를 특정 역할로 변경합니다. (관리자)")
@app_commands.describe(
    username="Roblox 본닉",
    role_name="그룹 역할 이름",
)
async def demote_to_role_cmd(
    interaction: discord.Interaction,
    username: str,
    role_name: str,
):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return 

    if not RANK_API_URL_ROOT or not RANK_API_KEY:
        await interaction.response.send_message(
            "랭킹 서버 설정이 되어 있지 않습니다.", ephemeral=True
        )
        return 

    await interaction.response.defer(ephemeral=True) 

    try:
        payload = {"username": username, "rank": role_name} 

        resp = requests.post(
            f"{RANK_API_URL_ROOT}/rank",
            json=payload,
            headers=_rank_api_headers(),
            timeout=30,
    )
    
        if resp.status_code == 200:
            data = resp.json()
            new_role = data.get("newRole", {})
            old_role = data.get("oldRole", {}) 

            old_rank_str = f"{old_role.get('name','?')} (Rank {old_role.get('rank','?')})"
            new_rank_str = f"{new_role.get('name','?')} (Rank {new_role.get('rank','?')})" 

            await interaction.followup.send(
                f"`{username}` 님을 역할 `{role_name}` 으로 변경했습니다.\n"
                f"실제 반영: {new_rank_str}",
                ephemeral=True,
            ) 

            guild = interaction.guild
            if guild:
                log_channel_id = get_log_channel(guild.id, "group_change")
                if log_channel_id:
                    try:
                        log_ch = guild.get_channel(log_channel_id) or await guild.fetch_channel(log_channel_id)
                        if log_ch:
                            embed = make_rank_log_embed(
                                RankLogType.DEMOTE,
                                target_name=username,
                                old_rank=old_rank_str,
                                new_rank=new_rank_str,
                                executor=interaction.user,
                            )
                            await log_ch.send(embed=embed)
                    except Exception as e:
                        print("[RANK_DEMOTE_LOG_ERROR]", repr(e)) 

        else:
            await interaction.followup.send(
                f"강등 실패 (HTTP {resp.status_code}): {resp.text}",
                ephemeral=True,
            )
    except Exception as e:
        await interaction.followup.send(f"요청 중 에러 발생: {e}", ephemeral=True)

@bot.tree.command(name="일괄승진", description="인증된 모든 유저를 특정 역할로 승진합니다. (관리자)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.describe(role_name="변경할 그룹 역할 이름 또는 숫자")
async def bulk_promote_to_role(interaction: discord.Interaction, role_name: str):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return 

    if not RANK_API_URL_ROOT or not RANK_API_KEY:
        await interaction.response.send_message(
            "랭킹 서버 설정이 되어 있지 않습니다.", ephemeral=True
        )
        return 

    await interaction.response.defer(ephemeral=True) 
    cursor.execute(
        "SELECT roblox_nick FROM users WHERE guild_id=? AND verified=1",
        (interaction.guild.id,),
    )
    verified_users = [row[0] for row in cursor.fetchall() if row[0]] 

    cursor.execute(
        "SELECT roblox_nick FROM forced_verified WHERE guild_id=?",
        (interaction.guild.id,),
    )
    forced_excluded = {row[0] for row in cursor.fetchall() if row[0]} 

    all_users = [u for u in verified_users if u not in forced_excluded] 

    if not all_users:
        await interaction.followup.send("인증된 유저가 없습니다.", ephemeral=True)
        return 

    total = len(all_users) 

    if total > 1000:
        await interaction.followup.send(
            f"{total}명 처리 예정 (약 {total // 60}분 소요)\n처리 시작합니다...",
            ephemeral=True,
        ) 

    BATCH_SIZE = 100
    all_results: list[dict] = [] 

    for i in range(0, total, BATCH_SIZE):
        batch = all_users[i:i + BATCH_SIZE] 

        try:
            payload = {"usernames": batch, "rank": role_name}
            resp = requests.post(
                f"{RANK_API_URL_ROOT}/bulk-promote-to-role",
                json=payload,
                headers=_rank_api_headers(),
                timeout=120,
            ) 

            if resp.status_code == 200:
                data = resp.json()
                all_results.extend(data.get("results", [])) 

            if (i + BATCH_SIZE) % 1000 == 0:
                await interaction.followup.send(
                    f"진행 중... {min(i + BATCH_SIZE, total)}/{total}명",
                    ephemeral=True,
                ) 

            await asyncio.sleep(1) 

        except Exception as e:
            print(f"Batch {i} error: {e}")
            continue 

    success_cnt = len([r for r in all_results if r.get("success")])
    fail_cnt = len([r for r in all_results if not r.get("success")]) 

    summary = make_bulk_rank_summary_embed(
        RankSummaryType.BULK_PROMOTE,
        role_name=role_name,
        total=total,
        success=success_cnt,
        failed=fail_cnt,
        executor=interaction.user,
    )
    await interaction.followup.send(embed=summary, ephemeral=True) 
    log_ch_id = get_log_channel(interaction.guild.id, "group_change")
    if log_ch_id:
        ch = interaction.guild.get_channel(log_ch_id) or await interaction.guild.fetch_channel(log_ch_id)
        if ch:
            await ch.send(embed=summary)

@bot.tree.command(name="그룹지정", description="이 서버의 로블록스 그룹을 설정합니다")
@app_commands.describe(그룹아이디="그룹 ID 입력")
@app_commands.default_permissions(administrator=True)
async def set_group(interaction: discord.Interaction, 그룹아이디: int):

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "관리자만 사용할 수 있습니다.", ephemeral=True
        )

    # DB에 저장 (이미 있는 함수 사용)
    set_guild_group_id(interaction.guild.id, 그룹아이디)

    await interaction.response.send_message(
        f"✅ 그룹이 `{그룹아이디}` 로 설정되었습니다."
    )
    
import aiohttp

@bot.tree.command(name="그룹정보", description="설정된 그룹 정보를 확인합니다")
async def group_info(interaction: discord.Interaction):

    group_id = get_guild_group_id(interaction.guild.id)

    if not group_id:
        return await interaction.response.send_message(
            "❌ 먼저 /그룹지정 으로 그룹을 설정하세요.", ephemeral=True
        )

    await interaction.response.defer()

    try:
        async with aiohttp.ClientSession() as session:

            # 그룹 기본 정보
            async with session.get(
                f"https://groups.roblox.com/v1/groups/{group_id}"
            ) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("그룹을 찾을 수 없습니다.")

                data = await resp.json()

            # 멤버 수
            async with session.get(
                f"https://groups.roblox.com/v1/groups/{group_id}/roles"
            ) as resp:
                roles_data = await resp.json()
                member_count = sum(r["memberCount"] for r in roles_data["roles"])

            # 아이콘
            async with session.get(
                f"https://thumbnails.roblox.com/v1/groups/icons?groupIds={group_id}&size=420x420&format=Png"
            ) as resp:
                icon_data = await resp.json()
                icon_url = icon_data["data"][0]["imageUrl"]

        embed = discord.Embed(
            title=data["name"],
            description=data["description"] or "설명 없음",
            color=discord.Color.blurple()
        )

        embed.add_field(name="📌 그룹 ID", value=str(data["id"]))
        embed.add_field(name="👥 멤버 수", value=f"{member_count:,}명")
        embed.add_field(
            name="👑 소유자",
            value=data["owner"]["username"] if data["owner"] else "없음"
        )

        embed.set_thumbnail(url=icon_url)
        embed.set_footer(text="Roblox Group Info")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"오류 발생: {e}")

@bot.tree.command(name="일괄강등", description="인증된 모든 유저를 특정 역할로 변경합니다. (관리자)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.describe(role_name="변경할 그룹 역할 이름 또는 숫자")
async def bulk_demote_to_role(interaction: discord.Interaction, role_name: str):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return 

    if not RANK_API_URL_ROOT or not RANK_API_KEY:
        await interaction.response.send_message(
            "랭킹 서버 설정이 되어 있지 않습니다.", ephemeral=True
        )
        return 

    await interaction.response.defer(ephemeral=True) 

    cursor.execute(
        "SELECT roblox_nick FROM users WHERE guild_id=? AND verified=1",
        (interaction.guild.id,),
    )
    verified_users = [row[0] for row in cursor.fetchall() if row[0]] 

    cursor.execute(
        "SELECT roblox_nick FROM forced_verified WHERE guild_id=?",
        (interaction.guild.id,),
    )
    forced_excluded = {row[0] for row in cursor.fetchall() if row[0]} 

    all_users = [u for u in verified_users if u not in forced_excluded] 

    if not all_users:
        await interaction.followup.send("인증된 유저가 없습니다.", ephemeral=True)
        return 

    total = len(all_users) 

    if total > 1000:
        await interaction.followup.send(
            f"{total}명 처리 예정 (약 {total // 60}분 소요)\n처리 시작합니다...",
            ephemeral=True,
        ) 

    BATCH_SIZE = 100
    all_results: list[dict] = [] 

    for i in range(0, total, BATCH_SIZE):
        batch = all_users[i:i + BATCH_SIZE] 

        try:
            payload = {"usernames": batch, "rank": role_name}
            resp = requests.post(
                f"{RANK_API_URL_ROOT}/bulk-demote-to-role",
                json=payload,
                headers=_rank_api_headers(),
                timeout=120,
            ) 

            if resp.status_code == 200:
                data = resp.json()
                all_results.extend(data.get("results", [])) 

            if (i + BATCH_SIZE) % 1000 == 0:
                await interaction.followup.send(
                    f"진행 중... {min(i + BATCH_SIZE, total)}/{total}명",
                    ephemeral=True,
                ) 

            await asyncio.sleep(1) 

        except Exception as e:
            print(f"Batch {i} error: {e}")
            continue 

    success_cnt = len([r for r in all_results if r.get("success")])
    fail_cnt = len([r for r in all_results if not r.get("success")]) 

    summary = make_bulk_rank_summary_embed(
        RankSummaryType.BULK_DEMOTE,
        role_name=role_name,
        total=total,
        success=success_cnt,
        failed=fail_cnt,
        executor=interaction.user,
    )
    await interaction.followup.send(embed=summary, ephemeral=True) 
    log_ch_id = get_log_channel(interaction.guild.id, "group_change")
    if log_ch_id:
        ch = interaction.guild.get_channel(log_ch_id) or await interaction.guild.fetch_channel(log_ch_id)
        if ch:
            await ch.send(embed=summary)

@bot.tree.command(name="페이아웃", description="로블닉으로 1회 그룹 페이아웃(DM 확인 안할시 못함)")
@app_commands.describe(
    유저="로블록스 닉네임",
    금액="지급할 로벅스 양 (정수)"
)
async def payout_once(interaction: discord.Interaction, 유저: str, 금액: int):
    if interaction.guild is None:
        await interaction.response.send_message("길드에서만 사용 가능합니다.", ephemeral=True)
        return

    caller_id = interaction.user.id
    if not (is_owner(interaction.user) or caller_id in PAYOUT_ALLOWED_USER_IDS):
        await interaction.response.send_message("권한이 없습니다.", ephemeral=True)
        return

    if 금액 <= 0:
        await interaction.response.send_message("금액은 1 이상이어야 합니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    roblox_username = 유저

    # 🔥 닉 → UserId (네 함수 사용)
    roblox_user_id = await roblox_get_user_id_by_username(roblox_username)

    if not roblox_user_id:
        await interaction.followup.send(f"❌ 존재하지 않는 로블록스 유저: {roblox_username}", ephemeral=True)
        return

    # 🔥 DM 확인
    recipients = {OWNER_ID} | ADDITIONAL_ADMIN_IDS
    confirm_text = (
        f"페이아웃 확인 요청:\n"
        f"- 실행자: {interaction.user} ({interaction.user.id})\n"
        f"- 로블닉: {roblox_username}\n"
        f"- UserId: {roblox_user_id}\n"
        f"- 지급량: {금액} R$"
    )

    view = PayoutConfirmView()
    approved = False

    for admin_id in recipients:
        try:
            admin_user = await bot.fetch_user(admin_id)
            await admin_user.send(content=confirm_text, view=view)

            await view.wait()
            if view.result:
                approved = True
                break

        except Exception:
            continue

    if not approved:
        await interaction.followup.send("❌ 페이아웃이 거부되었거나 확인되지 않았습니다.", ephemeral=True)
        return

    # 🔥 페이아웃 요청
    try:
        resp = requests.post(
            f"{API_BASE}/payout",
            json={
                "userId": roblox_username,
                "amount": 금액
            },
            headers=_rank_api_headers(),
            timeout=30,
        )
    except Exception as e:
        await interaction.followup.send(f"❌ 서버 요청 오류: {e}", ephemeral=True)
        return

    if resp.status_code != 200 or not resp.json().get("success"):
        await interaction.followup.send(
            f"❌ 페이아웃 실패: {resp.status_code} {resp.text}",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="그룹 페이아웃 완료",
        description=(
            f"`{roblox_username}` 에게 {금액} R$ 지급 완료\n"
            f"UserId: `{roblox_user_id}`"
        ),
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"요청자: {interaction.user} ({interaction.user.id})")

    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="동기화", description="슬래시 명령어를 동기화합니다.")
async def sync_commands(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return 

    await interaction.response.defer(ephemeral=True)
    try:
        if interaction.guild:
            synced = await bot.tree.sync(guild=interaction.guild)
            msg = f"{interaction.guild.name}({interaction.guild.id}) 길드에 {len(synced)}개 명령어 동기화 완료"
        else:
            synced = await bot.tree.sync()
            msg = f"전역에 {len(synced)}개 명령어 동기화 완료" 

        await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"동기화 중 오류: {e}", ephemeral=True)

@bot.tree.command(name="돈제거", description="유저의 돈을 제거합니다")
@app_commands.describe(
    user="대상 유저",
    amount="제거할 금액"
)
async def remove_money(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
):

    if amount <= 0:
        await interaction.response.send_message("금액 오류")
        return

    data = get_user(user.id)

    if not data:
        await interaction.response.send_message("유저 데이터 없음")
        return

    cur.execute(
        "UPDATE economy SET money = money - ? WHERE user_id=?",
        (amount, user.id)
    )

    conn.commit()

    await interaction.response.send_message(
        f"💸 돈 제거 완료\n유저 : {user.mention}\n제거 금액 : {amount}"
    )
    
@bot.tree.command(name="처벌추가", description="경고 횟수에 따른 처벌 규칙을 추가합니다. (관리자)")
@app_commands.describe(
    경고횟수="이 횟수에 도달하면 처벌 적용",
    처벌="적용할 처벌 종류",
    기간="타임아웃/뮤트일 때 지속 시간 (초 단위)"
)
@app_commands.choices(
    처벌=[
        app_commands.Choice(name="밴", value="ban"),
        app_commands.Choice(name="타임아웃", value="timeout"),
        app_commands.Choice(name="뮤트", value="mute"),
        app_commands.Choice(name="킥", value="kick"),
    ]
)
async def add_punish_rule(
    interaction: discord.Interaction,
    경고횟수: int,
    처벌: app_commands.Choice[str],
    기간: int | None = None,
):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("길드에서만 사용 가능합니다.", ephemeral=True)
        return

    punish_type = 처벌.value

    if punish_type in ("timeout", "mute") and (기간 is None or 기간 <= 0):
        await interaction.followup.send(
            "타임아웃/뮤트 처벌은 기간(초)을 1 이상으로 입력해야 합니다.",
            ephemeral=True,
        )
        return
    cursor.execute(
        """
        INSERT INTO punish_rules(guild_id, warn_count, punish_type, duration)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(guild_id, warn_count) DO UPDATE SET
            punish_type=excluded.punish_type,
            duration=excluded.duration
        """,
        (guild.id, 경고횟수, punish_type, 기간),
    )
    conn.commit()

    desc = f"경고 `{경고횟수}` 회 도달 시 `{punish_type}` 처벌을 적용합니다."
    if punish_type in ("timeout", "mute"):
        desc += f"\n기간: `{기간}` 초"

    embed = discord.Embed(
        title="✅ 처벌 규칙 추가/수정",
        color=discord.Color.green(),
        description=desc,
    )
    embed.add_field(
        name="설정자",
        value=f"{interaction.user.mention} (`{interaction.user.id}`)",
        inline=False,
    )

    await interaction.followup.send(embed=embed, ephemeral=True)

    await send_admin_log(
        guild,
        title="✅ 처벌 규칙 추가/수정",
        description="경고 횟수에 따른 자동 처벌 규칙이 설정되었습니다.",
        color=discord.Color.green(),
        fields=[
            ("경고 횟수", f"`{경고횟수}` 회", True),
            ("처벌", f"`{punish_type}`", True),
            (
                "기간",
                f"`{기간}` 초" if punish_type in ("timeout", "mute") else "해당 없음",
                True,
            ),
            ("설정자", f"{interaction.user.mention} (`{interaction.user.id}`)", False),
        ],
    )
    
import aiohttp

@bot.tree.command(name="그룹역할유저조회", description="그룹 역할에 속한 유저 목록을 조회합니다")
@app_commands.describe(역할아이디="그룹 역할 ID")
async def group_role_users(interaction: discord.Interaction, 역할아이디: int):

    group_id = get_guild_group_id(interaction.guild.id)

    if not group_id:
        return await interaction.response.send_message(
            "❌ 먼저 /그룹지정 을 해주세요.", ephemeral=True
        )

    await interaction.response.defer()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://groups.roblox.com/v1/groups/{group_id}/roles/{역할아이디}/users?limit=10"
            ) as resp:

                if resp.status != 200:
                    return await interaction.followup.send("데이터를 가져올 수 없습니다.")

                data = await resp.json()

        users = data["data"]
        next_cursor = data["nextPageCursor"]
        prev_cursor = data["previousPageCursor"]

        view = GroupUserView(group_id, 역할아이디, users, next_cursor, prev_cursor)

        await interaction.followup.send(
            embed=view.make_embed(),
            view=view
        )

    except Exception as e:
        await interaction.followup.send(f"오류 발생: {e}")
        
@bot.tree.command(name="백업", description="현재 서버의 역할, 채널, 유저 역할을 JSON 파일로 저장합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def backup_command(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    try:
        file_path = save_backup_data(guild)
        data = load_backup_data(guild.id)

        await interaction.response.send_message(
            f"백업 완료\n"
            f"파일: `{file_path}`\n"
            f"역할: **{len(data.get('roles', []))}개**\n"
            f"채널: **{len(data.get('channels', []))}개**\n"
            f"유저 역할 데이터: **{len(data.get('member_roles', {}))}명**",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"백업 실패: {e}", ephemeral=True)


@bot.tree.command(name="즉시백업", description="현재 서버를 즉시 백업합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def backup_now_command(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    try:
        file_path = save_backup_data(guild)
        await interaction.response.send_message(
            f"즉시 백업 완료: `{file_path}`",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"즉시 백업 실패: {e}",
            ephemeral=True
        )

@bot.tree.command(name="경고", description="유저에게 경고를 1회 부여합니다. (관리자)")
@app_commands.describe(
    user="경고를 줄 유저",
    이유="경고 사유"
)
async def warn(
    interaction: discord.Interaction,
    user: discord.Member,
    이유: str | None = None,
):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("길드에서만 사용 가능합니다.", ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.followup.send("자기 자신에게는 경고를 줄 수 없습니다.", ephemeral=True)
        return
    cursor.execute(
        "SELECT warns FROM warnings WHERE guild_id=? AND user_id=?",
        (guild.id, user.id),
    )
    row = cursor.fetchone()
    current_warns = row[0] if row else 0
    new_warns = current_warns + 1
    cursor.execute(
        """
        INSERT INTO warnings(guild_id, user_id, warns)
        VALUES(?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET warns=excluded.warns
        """,
        (guild.id, user.id, new_warns),
    )
    conn.commit()
    cursor.execute(
        """
        INSERT INTO mod_logs(guild_id, user_id, action, moderator_id, reason, created_at)
        VALUES(?, ?, ?, ?, ?, datetime('now'))
        """,
        (guild.id, user.id, "warn", interaction.user.id, 이유 or None),
    )
    conn.commit()
    user_embed = discord.Embed(
        title="⚠️ 경고 부여",
        color=discord.Color.orange(),
        description=f"{user.mention} 님에게 경고 1회가 부여되었습니다.",
    )
    user_embed.add_field(name="현재 경고 횟수", value=f"`{new_warns}` 회", inline=True)
    user_embed.add_field(name="사유", value=이유 or "사유 없음", inline=False)
    user_embed.add_field(
        name="실행자",
        value=f"{interaction.user.mention} (`{interaction.user.id}`)",
        inline=False,
    )

    await interaction.followup.send(embed=user_embed, ephemeral=True)
    await send_admin_log(
        guild,
        title="⚠️ 경고 부여",
        description="관리자가 유저에게 경고를 부여했습니다.",
        color=discord.Color.orange(),
        fields=[
            ("대상 유저", f"{user.mention} (`{user.id}`)", False),
            ("현재 경고 횟수", f"`{new_warns}` 회", True),
            ("사유", 이유 or "사유 없음", False),
            ("실행자", f"{interaction.user.mention} (`{interaction.user.id}`)", False),
        ],
    )
    cursor.execute(
        "SELECT punish_type, duration FROM punish_rules WHERE guild_id=? AND warn_count=?",
        (guild.id, new_warns),
     )
    rule = cursor.fetchone()
    if rule:
        punish_type, duration = rule
        await apply_punishment(guild, user, punish_type, duration, interaction.user, 이유)

# @bot.tree.command(
#     name="일괄닉네임변경",
#     description="인증된 유저의 닉네임을 [랭크] 본닉 형식으로 변경합니다. (관리자)"
# )
# @app_commands.guilds(discord.Object(id=GUILD_ID))
# async def bulk_nickname_change(interaction: discord.Interaction):
#     if not is_admin(interaction.user):
#         await interaction.response.send_message(
#             "관리자만 사용할 수 있습니다.",
#             ephemeral=True
#         )
#         return

#     await interaction.response.defer(ephemeral=True)

#     try:
#         cursor.execute(
#             "SELECT discord_id, roblox_nick FROM users WHERE guild_id=? AND verified=1",
#             (interaction.guild.id,),
#         )
#         users_data = cursor.fetchall()

#         if not users_data:
#             await interaction.followup.send(
#                 "인증된 유저가 없습니다.",
#                 ephemeral=True
#             )
#             return

#         usernames = [row[1] for row in users_data]

#         resp = requests.post(
#             f"{RANK_API_URL_ROOT}/bulk-status",
#             json={"usernames": usernames},
#             headers=_rank_api_headers(),
#             timeout=60,
#         )

#         if resp.status_code != 200:
#             await interaction.followup.send(
#                 f"랭크 조회 실패 (HTTP {resp.status_code})",
#                 ephemeral=True
#             )
#             return

#         data = resp.json()

#         rank_map = {}
#         for r in data.get("results", []):
#             if r.get("success"):
#                 role_info = r.get("role", {}) or {}
#                 rank_map[r["username"]] = role_info.get("name", "?")

#         updated = 0
#         failed = 0

#         for discord_id, roblox_nick in users_data:
#             try:
#                 member = interaction.guild.get_member(discord_id)
#                 if not member:
#                     failed += 1
#                     continue

#                 rank_name = rank_map.get(roblox_nick, "?") or "?"

#                 if " | " in rank_name:
#                     rank_name = rank_name.split(" | ")[-1]

#                 new_nick = f"[{rank_name}] {roblox_nick}"

#                 if len(new_nick) > 32:
#                     new_nick = new_nick[:32]

#                 await member.edit(nick=new_nick)
#                 updated += 1

#             except Exception as e:
#                 print(f"닉네임 변경 실패 {roblox_nick}: {e}")
#                 failed += 1

#         embed = discord.Embed(
#             title="일괄 닉네임 변경 완료",
#             color=discord.Color.blue(),
#         )
#         embed.add_field(name="성공", value=str(updated), inline=True)
#         embed.add_field(name="실패", value=str(failed), inline=True)
#         embed.add_field(name="형식", value="[랭크] 로블 본닉", inline=False)

#         await interaction.followup.send(embed=embed, ephemeral=True)

#     except Exception as e:
#         await interaction.followup.send(
#             f"요청 중 에러 발생: {e}",
#             ephemeral=True
#         )

@bot.tree.command(name="로그채널지정", description="로그 채널을 설정합니다. (관리자)")
@app_commands.describe(
    인증="인증 로그 채널",
    그룹변경="그룹변경 로그 채널",
    관리자="관리자 로그 채널",
    보안="보안 로그 채널",
    개발자="개발자 로그 채널",
    아이템="아이템 구매 로그 채널",
    공지="공지 로그 채널"
)
async def set_log_channels(
    interaction: discord.Interaction,
    인증: discord.TextChannel | None = None,
    그룹변경: discord.TextChannel | None = None,
    관리자: discord.TextChannel | None = None,
    보안: discord.TextChannel | None = None,
    개발자: discord.TextChannel | None = None,
    아이템: discord.TextChannel | None = None,
    공지: discord.TextChannel | None = None,
):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("길드에서만 사용 가능합니다.", ephemeral=True)
        return

    changed = []

    if 인증 is not None:
        set_log_channel(guild.id, "verify", 인증.id)
        changed.append(f"인증: {인증.mention}")

    if 그룹변경 is not None:
        set_log_channel(guild.id, "group_change", 그룹변경.id)
        changed.append(f"그룹변경: {그룹변경.mention}")

    if 관리자 is not None:
        set_log_channel(guild.id, "admin", 관리자.id)
        changed.append(f"관리자: {관리자.mention}")

    if 보안 is not None:
        set_log_channel(guild.id, "security", 보안.id)
        changed.append(f"보안: {보안.mention}")

    if 개발자 is not None:
        set_log_channel(guild.id, "dev", 개발자.id)
        changed.append(f"개발자: {개발자.mention}")

    if 아이템 is not None:
        set_log_channel(guild.id, "item", 아이템.id)
        changed.append(f"아이템: {아이템.mention}")

    if 공지 is not None:
        set_log_channel(guild.id, "announce", 공지.id)
        changed.append(f"공지: {공지.mention}")

    if not changed:
        await interaction.response.send_message(
            "변경된 채널이 없습니다. 최소 한 개 이상 지정해 주세요.",
            ephemeral=True
        )
        return

    msg = "다음 로그 채널이 설정되었습니다:\n" + "\n".join(changed)

    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="블랙리스트", description="블랙리스트 그룹을 관리합니다. (관리자)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.describe(
    group_id="Roblox 그룹 ID",
    action="add (추가) 또는 remove (제거)",
)
async def manage_blacklist(interaction: discord.Interaction, group_id: int, action: str = "add"):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return 

    if action.lower() == "add":
        try:
            cursor.execute(
                "INSERT INTO blacklist(guild_id, group_id) VALUES(?, ?)",
                (interaction.guild.id, group_id),
            )
            conn.commit()
            await interaction.response.send_message(
                f" 그룹 ID `{group_id}` 을(를) 블랙리스트에 추가했습니다.", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"추가 실패: {e}", ephemeral=True)
    else:
        cursor.execute(
            "DELETE FROM blacklist WHERE guild_id=? AND group_id=?",
            (interaction.guild.id, group_id),
        )
        conn.commit()
        await interaction.response.send_message(
            f" 그룹 ID `{group_id}` 을(를) 블랙리스트에서 제거했습니다.", ephemeral=True
        ) 

@bot.tree.command(name="블랙리스트목록", description="블랙리스트 그룹 목록을 봅니다. (관리자)")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def view_blacklist(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return 

    cursor.execute("SELECT group_id FROM blacklist WHERE guild_id=?", (interaction.guild.id,))
    rows = cursor.fetchall() 

    embed = discord.Embed(title="블랙리스트 그룹", color=discord.Color.red()) 

    if not rows:
        embed.description = "블랙리스트에 그룹이 없습니다."
    else:
        group_ids = [str(row[0]) for row in rows]
        embed.description = "\n".join(group_ids) 

    await interaction.response.send_message(embed=embed, ephemeral=True) 

# @bot.tree.command(name="역할전체변경", description="모든 유저의 역할을 한 역할로 통일합니다. (위험)")
# async def set_all_role(interaction: discord.Interaction):
#     guild = interaction.guild

#     if guild.id != GUILD_ID:
#         await interaction.response.send_message(
#             "이 명령어는 지정된 서버에서만 사용할 수 있습니다.",
#             ephemeral=True
#         )
#         return

#     target_role = guild.get_role(TARGET_ROLE_ID)
#     if not target_role:
#         await interaction.response.send_message(
#             "대상 역할을 찾을 수 없습니다.",
#             ephemeral=True
#         )
#         return

#     await interaction.response.send_message(
#         "모든 멤버 역할 변경 시작...",
#         ephemeral=True
#     )

#     success = 0
#     failed = 0
#     skipped = 0

#     for member in guild.members:
#         if member.bot:
#             continue
#         if guild.me.top_role <= member.top_role:
#             skipped += 1
#             continue

#         try:
#             everyone = member.roles[0]
#             new_roles = [everyone, target_role]

#             await member.edit(roles=new_roles)
#             success += 1
#             await asyncio.sleep(0.3)

#         except discord.Forbidden:
#             print(f"{member} 권한 부족으로 스킵")
#             failed += 1

#         except Exception as e:
#             print(f"{member} 역할 변경 실패: {e}")
#             failed += 1

#     await interaction.followup.send(
#         f"역할 변경 완료\n"
#         f"성공: {success}명\n"
#         f"실패: {failed}명\n"
#         f"위상/조건으로 스킵: {skipped}명",
#         ephemeral=True
#     )

URL_REGEX = re.compile(r"https?://\S+")
_user_message_cache: dict[tuple[int, int], list[float]] = {}
xp_cooldown: dict[int, float] = {}

# 기존 XP 처리 함수로 분리
async def handle_xp(message: discord.Message):
    if message.author.bot:
        return

    user_id = message.author.id
    now = time.time()

    if user_id in xp_cooldown:
        if now - xp_cooldown[user_id] < 30:
            return

    xp_cooldown[user_id] = now

    user = get_user(user_id)  # 기존 함수 그대로 사용 (user = (id, money, last_daily, exp, level))
    exp = user[3]
    level = user[4]

    gain = random.randint(10, 20)
    exp += gain

    need = 50 + (level * 25)

    if exp >= need:
        level += 1
        exp -= need
        reward = level * 50

        cur.execute(
            "UPDATE economy SET money = money + ? WHERE user_id=?",
            (reward, user_id)
        )

    cur.execute(
        "UPDATE economy SET exp=?, level=? WHERE user_id=?",
        (exp, level, user_id)
    )

    conn.commit()


def _is_link_blocked(guild_id: int, member: discord.Member, content: str) -> bool:
    if not URL_REGEX.search(content):
        return False

    cursor.execute(
        "SELECT mode, roleid FROM linkpolicy WHERE guildid=?",
        (guild_id,),
    )
    row = cursor.fetchone()
    if not row:
        return False

    mode, roleid = row
    mode = mode.lower()

    if mode == "all":
        return False
    if mode == "none":
        return True
    if mode == "role":
        if roleid is None:
            return True
        role = member.guild.get_role(roleid)
        if not role:
            return True
        if role not in member.roles:
            return True
        return False
    return False


def _insert_link_log(guild_id: int, user_id: int, url: str) -> None:
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    cursor.execute(
        """
        INSERT INTO linklogs (guildid, userid, url, createdat)
        VALUES (?, ?, ?, ?)
        """,
        (guild_id, user_id, url, now),
    )
    conn.commit()


def _get_spam_setting(guild_id: int):
    cursor.execute(
        "SELECT window_sec, max_messages, action, duration FROM spamsettings WHERE guildid=?",
        (guild_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "window": row[0],
        "max": row[1],
        "action": row[2],
        "duration": row[3],
    }


def _insert_spam_log(guild_id: int, user_id: int, msg_count: int, window_sec: int, action: str) -> None:
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    cursor.execute(
        """
        INSERT INTO spamlogs (guildid, userid, messages, window_sec, action, createdat)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (guild_id, user_id, msg_count, window_sec, action, now),
    )
    conn.commit()


async def send_security_log(
    guild: discord.Guild,
    title: str,
    description: str,
    color: discord.Color = discord.Color.red(),
):
    log_ch_id = get_log_channel(guild.id, "security")
    if not log_ch_id:
        return

    ch = guild.get_channel(log_ch_id) or await guild.fetch_channel(log_ch_id)
    if not ch:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    await ch.send(embed=embed)
    
@bot.tree.command(name="돈", description="24시간마다 돈 받기")
async def daily(interaction: discord.Interaction):

    user = get_user(interaction.user.id)
    now = int(time.time())

    if now - user[2] < 86400:

        remain = 86400 - (now - user[2])
        h = remain // 3600
        m = (remain % 3600) // 60

        await interaction.response.send_message(
            f"⏳ {h}시간 {m}분 후 다시 받을 수 있습니다."
        )
        return

    reward = random.randint(100,300)

    cur.execute(
        "UPDATE economy SET money = money + ?, last_daily=? WHERE user_id=?",
        (reward, now, interaction.user.id)
    )

    conn.commit()

    await interaction.response.send_message(
        f"💰 {reward}원을 받았습니다!"
    )

@bot.tree.command(name="도박", description="돈을 걸고 도박합니다")
@app_commands.describe(amount="도박 금액")
async def gamble(interaction: discord.Interaction, amount: int):

    user = get_user(interaction.user.id)

    if amount <= 0:
        await interaction.response.send_message("금액 오류")
        return

    if user[1] < amount:
        await interaction.response.send_message("돈이 부족합니다")
        return

    r = random.random()

    if r <= 0.50:
        cur.execute(
            "UPDATE economy SET money = money - ? WHERE user_id=?",
            (amount, interaction.user.id)
        )
        conn.commit()

        await interaction.response.send_message(
            f"💀 도박 실패\n잃은 돈 : {amount}"
        )
        return

    elif r <= 0.85:
        multi = 2
    elif r <= 0.95:
        multi = 3
    elif r <= 0.99:
        multi = 4
    else:
        multi = 5

    win = amount * multi

    cur.execute(
        "UPDATE economy SET money = money + ? WHERE user_id=?",
        (win, interaction.user.id)
    )

    conn.commit()

    await interaction.response.send_message(
        f"🎰 도박 성공!\n배율 : x{multi}\n획득 : {win}"
    )

@bot.tree.command(name="아이템샵", description="서버 아이템을 보여줍니다.")
async def shop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("길드에서만 사용 가능합니다.", ephemeral=True)
        return

    cursor.execute(
        """
        SELECT name, price, type, role_id, level, exp
        FROM shop_items
        WHERE guild_id=?
        ORDER BY price ASC
        """,
        (guild.id,),
    )
    items = cursor.fetchall()
    if not items:
        await interaction.followup.send("상점에 등록된 아이템이 없습니다.", ephemeral=True)
        return

    view = ShopView(guild, items)
    embed = view.make_page_embed()
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class PayoutConfirmView(View):
    def __init__(self):
        super().__init__(timeout=3600)  # 1시간 후 자동 종료
        self.result = None  # 승인(True) / 거부(False)

    @discord.ui.button(label="✅ 승인", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: Button):
        self.result = True
        for child in self.children:
            child.disabled = True  # 버튼 비활성화
        await interaction.response.edit_message(content="✅ 승인 완료", view=self)
        self.stop()

    @discord.ui.button(label="❌ 거부", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: Button):
        self.result = False
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ 거부 완료", view=self)
        self.stop()
    
class DramaticGambleModal(Modal, title="극적 도박"):

    amount = TextInput(
        label="도박 금액",
        placeholder="금액 입력",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):

        try:
            amount = int(self.amount.value)
        except:
            await interaction.response.send_message("금액 오류", ephemeral=True)
            return

        user = get_user(interaction.user.id)

        if amount <= 0:
            await interaction.response.send_message("금액 오류", ephemeral=True)
            return

        if user[1] < amount:
            await interaction.response.send_message("돈이 부족합니다", ephemeral=True)
            return

        # 잭팟 적립 (1%)
        jackpot_add = int(amount * 0.01)

        cur.execute(
            "UPDATE jackpot SET money = money + ? WHERE id=1",
            (jackpot_add,)
        )

        r = random.random()

        # 잭팟 터짐 (0.1%)
        if r >= 0.999:

            cur.execute("SELECT money FROM jackpot WHERE id=1")
            jackpot_money = cur.fetchone()[0]

            cur.execute(
                "UPDATE economy SET money = money + ? WHERE user_id=?",
                (jackpot_money, interaction.user.id)
            )

            cur.execute(
                "UPDATE jackpot SET money = 0 WHERE id=1"
            )

            conn.commit()

            await interaction.response.send_message(
                f"👑 전설의 잭팟!!!\n획득 : {jackpot_money}"
            )
            return

        # 실패
        if r <= 0.70:

            cur.execute(
                "UPDATE economy SET money = money - ? WHERE user_id=?",
                (amount, interaction.user.id)
            )
            conn.commit()

            await interaction.response.send_message(
                f"💀 극적 도박 실패\n잃은 돈 : {amount}"
            )
            return

        elif r <= 0.90:
            multi = 2
        elif r <= 0.98:
            multi = 5
        elif r <= 0.999:
            multi = 10

        win = amount * multi

        cur.execute(
            "UPDATE economy SET money = money + ? WHERE user_id=?",
            (win, interaction.user.id)
        )

        conn.commit()

        await interaction.response.send_message(
            f"🔥 극적 도박 성공!\n배율 : x{multi}\n획득 : {win}"
        )

@bot.tree.command(name="경제그래프")
async def economy_graph(interaction: discord.Interaction):

    cur.execute("""
    SELECT money FROM economy
    ORDER BY money DESC
    LIMIT 10
    """)

    data = [x[0] for x in cur.fetchall()]

    if not data:
        await interaction.response.send_message("데이터 없음")
        return

    avg = sum(data) // len(data)

    # 📊 그래프 생성
    plt.figure()
    plt.plot(data)
    plt.title("Top 10 Money")
    plt.xlabel("Rank")
    plt.ylabel("Money")

    # PNG로 저장 (메모리)
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()

    file = discord.File(fp=buf, filename="economy.png")

    await interaction.response.send_message(
        content=f"📊 평균 돈: {avg}",
        file=file
    )

@bot.tree.command(name="극적도박", description="극적인 도박을 합니다")
async def dramatic_gamble(interaction: discord.Interaction):

    modal = DramaticGambleModal()
    await interaction.response.send_modal(modal)

@bot.tree.command(name="잭팟", description="현재 잭팟 금액")
async def jackpot(interaction: discord.Interaction):

    cur.execute("SELECT money FROM jackpot WHERE id=1")
    money = cur.fetchone()[0]

    await interaction.response.send_message(
        f"🎰 현재 잭팟 : {money}"
    )
    
@bot.tree.command(name="구매", description="상점 아이템을 구매합니다.")
@app_commands.describe(이름="구매할 아이템 이름")
async def buy(interaction: discord.Interaction, 이름: str):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    member = interaction.user
    if guild is None:
        await interaction.followup.send("길드에서만 사용 가능합니다.", ephemeral=True)
        return
    cursor.execute(
        """
        SELECT price, type, role_id, level, exp
        FROM shop_items
        WHERE guild_id=? AND name=?
        """,
        (guild.id, 이름),
    )
    row = cursor.fetchone()
    if not row:
        await interaction.followup.send("해당 이름의 아이템이 없습니다.", ephemeral=True)
        return

    price, item_type, role_id, level_val, exp_val = row
    user = get_user(member.id)   (user_id, money, last_daily, exp, level)
    _, money, _, cur_exp, cur_level = user

    if money < price:
        await interaction.followup.send("잔액이 부족합니다.", ephemeral=True)
        return
    new_money = money - price
    cur.execute(
        "UPDATE economy SET money=? WHERE user_id=?",
        (new_money, member.id),
    )

    detail = ""
    if item_type == "role":
        if role_id:
            role = guild.get_role(role_id)
            if role:
                await guild.get_member(member.id).add_roles(role, reason="아이템 구매")
                detail = f"역할 {role.mention} 지급 완료."
            else:
                detail = "역할을 찾을 수 없습니다."
        else:
            detail = "이 아이템에는 역할 ID가 설정되어 있지 않습니다."

    elif item_type == "level":
        if level_val is not None:
            add_level = int(level_val)
            new_level = cur_level + add_level
            cur.execute(
                "UPDATE economy SET level=? WHERE user_id=?",
                (new_level, member.id),
            )
            detail = f"레벨 {add_level} 상승! (현재 레벨: {new_level})"
        else:
            detail = "이 아이템에는 레벨 값이 설정되어 있지 않습니다."

    elif item_type == "exp":
        if exp_val is not None:
            add_exp = int(exp_val)
            new_exp = cur_exp + add_exp
            cur.execute(
                "UPDATE economy SET exp=? WHERE user_id=?",
                (new_exp, member.id),
            )
            detail = f"경험치 {add_exp} 획득! (현재 경험치: {new_exp})"
        else:
            detail = "이 아이템에는 경험치 값이 설정되어 있지 않습니다."

    else:
        await interaction.followup.send("알 수 없는 아이템 타입입니다.", ephemeral=True)
        return

    conn.commit()
    user_embed = discord.Embed(
        title="✅ 아이템 구매 완료",
        color=discord.Color.green(),
        description=(
            f"아이템: `{이름}`\n"
            f"가격: `{price}`\n"
            f"잔액: `{new_money}`\n\n"
            f"{detail}"
        ),
    )
    await interaction.followup.send(embed=user_embed, ephemeral=True)
    log_ch_id = get_log_channel(guild.id, "item")
    if log_ch_id:
        log_ch = guild.get_channel(log_ch_id) or await guild.fetch_channel(log_ch_id)
        if log_ch:
            log_embed = discord.Embed(
                title="🔵 아이템 구매",
                color=discord.Color.blue(),
            )
            log_embed.add_field(
                name="구매자",
                value=f"{member.mention} (`{member.id}`)",
                inline=False,
            )
            log_embed.add_field(name="아이템 이름", value=f"`{이름}`", inline=True)
            log_embed.add_field(name="가격", value=f"`{price}`", inline=True)
            log_embed.add_field(name="타입", value=f"`{item_type}`", inline=True)
            log_embed.add_field(name="구매 후 잔액", value=f"`{new_money}`", inline=False)

            if item_type == "role" and role_id:
                role = guild.get_role(role_id)
                if role:
                    log_embed.add_field(
                        name="지급된 역할",
                        value=f"{role.mention} (`{role.id}`)",
                        inline=False,
                    )
            if item_type == "level" and level_val is not None:
                log_embed.add_field(
                    name="레벨 증가",
                    value=f"+{int(level_val)} (이전: {cur_level})",
                    inline=False,
                )
            if item_type == "exp" and exp_val is not None:
                log_embed.add_field(
                    name="경험치 증가",
                    value=f"+{int(exp_val)} (이전: {cur_exp})",
                    inline=False,
                )

            await log_ch.send(embed=log_embed)

@bot.tree.command(name="아이템추가", description="상점 아이템을 추가합니다. (관리자)")
@app_commands.describe(
    이름="아이템 이름",
    가격="아이템 가격 (정수)",
    종류="아이템 종류 (역할, 레벨, 경험치)",
    역할="역할 아이템일 경우 지급할 역할",
    레벨="레벨 아이템일 경우 부여할 레벨 값",
    경험치="경험치 아이템일 경우 부여할 경험치 양",
)
@app_commands.choices(
    종류=[
        app_commands.Choice(name="역할", value="role"),
        app_commands.Choice(name="레벨", value="level"),
        app_commands.Choice(name="경험치", value="exp"),
    ]
)
async def add_item(
    interaction: discord.Interaction,
    이름: str,
    가격: int,
    종류: app_commands.Choice[str],
    역할: discord.Role | None = None,
    레벨: int | None = None,
    경험치: int | None = None,
):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("길드에서만 사용 가능합니다.", ephemeral=True)
        return

    item_type = 종류.value

    if item_type == "role":
        if 역할 is None:
            await interaction.response.send_message("역할 아이템은 역할 옵션이 필수입니다.", ephemeral=True)
            return
        role_id = 역할.id
        level_val = None
        exp_val = None

    elif item_type == "level":
        if 레벨 is None:
            await interaction.response.send_message("레벨 아이템은 레벨 값을 넣어야 합니다.", ephemeral=True)
            return
        role_id = None
        level_val = 레벨
        exp_val = None

    else:
        if 경험치 is None:
            await interaction.response.send_message("경험치 아이템은 경험치 값을 넣어야 합니다.", ephemeral=True)
            return
        role_id = None
        level_val = None
        exp_val = 경험치
    cursor.execute(
        """
        INSERT INTO shop_items(guild_id, name, price, type, role_id, level, exp)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (guild.id, 이름, 가격, item_type, role_id, level_val, exp_val),
    )
    conn.commit()
    await interaction.response.send_message(f"✅ `{이름}` 아이템을 추가했습니다.", ephemeral=True)
    log_ch_id = get_log_channel(guild.id, "item")
    if log_ch_id:
        log_ch = guild.get_channel(log_ch_id) or await guild.fetch_channel(log_ch_id)
        if log_ch:
            embed = discord.Embed(
                title="🟢 아이템 추가",
                color=discord.Color.green(),
            )
            embed.add_field(name="아이템 이름", value=f"`{이름}`", inline=True)
            embed.add_field(name="가격", value=f"`{가격}`", inline=True)
            embed.add_field(name="타입", value=f"`{item_type}`", inline=True)

            if item_type == "role" and role_id:
                role = guild.get_role(role_id)
                if role:
                    embed.add_field(name="역할", value=f"{role.mention} (`{role.id}`)", inline=False)
            if item_type == "level" and level_val is not None:
                embed.add_field(name="레벨", value=f"+{level_val}", inline=False)
            if item_type == "exp" and exp_val is not None:
                embed.add_field(name="경험치", value=f"+{exp_val}", inline=False)

            embed.add_field(
                name="추가한 유저",
                value=f"{interaction.user.mention} (`{interaction.user.id}`)",
                inline=False,
            )
            await log_ch.send(embed=embed)
            
@bot.tree.command(name="엠베드생성", description="모달로 엠베드 생성")
async def embed_create(interaction: discord.Interaction):
    await interaction.response.send_modal(EmbedModal())
    
@bot.tree.command(name="기브어웨이", description="기브어웨이 생성")
@app_commands.describe(상품="상품명", 시간="초 단위", 인원="당첨자 수")
async def giveaway(interaction: discord.Interaction, 상품: str, 시간: int, 인원: int):

    embed = discord.Embed(
        title="🎉 기브어웨이",
        description=f"상품: **{상품}**\n시간: {시간}초\n🎉 눌러 참여!",
        color=discord.Color.red()
    )

    message = await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()

    await msg.add_reaction("🎉")

    await asyncio.sleep(시간)

    msg = await interaction.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")

    if not reaction:
        return await interaction.followup.send("참여자가 없습니다 😢")

    users = [user async for user in reaction.users() if not user.bot]

    if len(users) == 0:
        return await interaction.followup.send("참여자가 없습니다 😢")

    winners = random.sample(users, min(인원, len(users)))

    winner_mentions = ", ".join([user.mention for user in winners])

    await interaction.followup.send(f"🎉 당첨자: {winner_mentions}")

@bot.tree.command(name="아이템삭제", description="상점에서 아이템을 삭제합니다. (관리자)")
@app_commands.describe(이름="삭제할 아이템 이름")
async def delete_item(interaction: discord.Interaction, 이름: str):
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("길드에서만 사용 가능합니다.", ephemeral=True)
        return
    cursor.execute(
        """
        SELECT price, type, role_id, level, exp
        FROM shop_items
        WHERE guild_id=? AND name=?
        """,
        (guild.id, 이름),
    )
    row = cursor.fetchone()
    if not row:
        await interaction.response.send_message("해당 이름의 아이템이 없습니다.", ephemeral=True)
        return

    price, item_type, role_id, level_val, exp_val = row
    cursor.execute(
        "DELETE FROM shop_items WHERE guild_id=? AND name=?",
        (guild.id, 이름),
    )
    conn.commit()

    await interaction.response.send_message(f"🗑 `{이름}` 아이템을 삭제했습니다.", ephemeral=True)
    log_ch_id = get_log_channel(guild.id, "item")
    if log_ch_id:
        log_ch = guild.get_channel(log_ch_id) or await guild.fetch_channel(log_ch_id)
        if log_ch:
            embed = discord.Embed(
                title="🔴 아이템 삭제",
                color=discord.Color.red(),
            )
            embed.add_field(name="아이템 이름", value=f"`{이름}`", inline=True)
            embed.add_field(name="가격", value=f"`{price}`", inline=True)
            embed.add_field(name="타입", value=f"`{item_type}`", inline=True)

            if item_type == "role" and role_id:
                role = guild.get_role(role_id)
                if role:
                    embed.add_field(name="역할", value=f"{role.mention} (`{role.id}`)", inline=False)
            if item_type == "level" and level_val is not None:
                embed.add_field(name="레벨", value=f"+{level_val}", inline=False)
            if item_type == "exp" and exp_val is not None:
                embed.add_field(name="경험치", value=f"+{exp_val}", inline=False)

            embed.add_field(
                name="삭제한 유저",
                value=f"{interaction.user.mention} (`{interaction.user.id}`)",
                inline=False,
            )
            await log_ch.send(embed=embed)
@bot.tree.command(name="유저", description="유저 정보 확인")
async def userinfo(interaction: discord.Interaction, member: discord.Member | None = None):
    if member is None:
        member = interaction.user

    guild = interaction.guild
    user = get_user(member.id)
    money = user[1]
    exp = user[3]
    level = user[4]
    need = 50 + (level * 25)

    embed = discord.Embed(title=f"{member.name} 정보")
    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(name="💰 돈", value=money, inline=True)
    embed.add_field(name="⭐ 레벨", value=level, inline=True)
    embed.add_field(name="📊 EXP", value=f"{exp}/{need}", inline=True)
    cursor.execute(
        "SELECT warns FROM warnings WHERE guild_id=? AND user_id=?",
        (guild.id, member.id),
    )
    row = cursor.fetchone()
    warn_count = row[0] if row else 0
    embed.add_field(name="⚠️ 경고 횟수", value=f"{warn_count}회", inline=True)

    cursor.execute(
        """
        SELECT action, moderator_id, reason, created_at
        FROM mod_logs
        WHERE guild_id=? AND user_id=?
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (guild.id, member.id),
    )
    logs = cursor.fetchall()
    if logs:
        lines = []
        for action, moderator_id, reason, created_at in logs:
            mod = guild.get_member(moderator_id)
            mod_name = mod.mention if mod else f"`{moderator_id}`"
            lines.append(
                f"[{created_at}] `{action}`\n"
                f"- 처리자: {mod_name}\n"
                f"- 사유: {reason or '사유 없음'}"
            )
        history_text = "\n\n".join(lines)
    else:
        history_text = "최근 제재 내역 없음"
    embed.add_field(
        name="📜 최근 제재 내역 (최대 5개)",
        value=history_text[:1024],
        inline=False,
    )

    cursor.execute(
        """
        SELECT roblox_nick, roblox_user_id, verified
        FROM users
        WHERE discord_id=? AND guild_id=?
        """,
        (member.id, guild.id),
    )
    urow = cursor.fetchone()
    if urow:
        roblox_nick, roblox_user_id, verified = urow
        embed.add_field(
            name="🧩 로블 인증",
            value=(
                f"상태: `{'인증됨' if verified else '미인증'}`\n"
                f"닉네임: `{roblox_nick}`\n"
                f"UserId: `{roblox_user_id}`"
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="🧩 로블 인증",
            value="등록된 인증 정보가 없습니다.",
            inline=False,
        )

    cursor.execute(
        "SELECT 1 FROM forced_verified WHERE discord_id=? AND guild_id=?",
        (member.id, guild.id),
    )
    forced = cursor.fetchone() is not None
    embed.add_field(
        name="🔒 강제인증",
        value="예" if forced else "아니오",
        inline=True,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)



@bot.tree.command(name="경제초기화", description="경제 데이터를 초기화합니다. (제작자)")
async def reset_economy(interaction: discord.Interaction):

    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            "❌ 제작자만 사용할 수 있습니다.",
            ephemeral=True
        )
        return

    cur.execute(
        "DELETE FROM economy"
    )

    conn.commit()

    await interaction.response.send_message(
        "💣 모든 경제 데이터가 초기화되었습니다."
    )

@bot.tree.command(name="레벨추가", description="유저 레벨을 추가합니다.")
@app_commands.describe(
    유저="레벨을 추가할 유저",
    레벨="추가할 레벨"
)
async def add_level(
    interaction: discord.Interaction,
    유저: discord.Member,
    레벨: int
):

    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "관리자만 사용 가능합니다.",
            ephemeral=True
        )
        return

    if 레벨 <= 0:
        await interaction.response.send_message(
            "1 이상의 숫자를 입력하세요.",
            ephemeral=True
        )
        return

    user = get_user(유저.id)
    current_level = user[4]

    new_level = current_level + 레벨

    cur.execute(
        "UPDATE economy SET level=? WHERE user_id=?",
        (new_level, 유저.id)
    )

    conn.commit()

    embed = discord.Embed(
        title="⭐ 레벨 추가",
        color=discord.Color.green()
    )

    embed.add_field(name="대상", value=유저.mention)
    embed.add_field(name="추가 레벨", value=f"+{레벨}")
    embed.add_field(name="현재 레벨", value=new_level)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="경제백업다운로드", description="경제 백업 파일을 다운로드합니다.")
async def download_backup(interaction: discord.Interaction):

    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용 가능", ephemeral=True)
        return

    try:

        file = discord.File("economy_backup.json")

        await interaction.response.send_message(
            content="📦 경제 백업 파일입니다.",
            file=file,
            ephemeral=True
        )

    except:

        await interaction.response.send_message(
            "❌ 백업 파일이 없습니다.\n먼저 `/경제백업`을 실행하세요.",
            ephemeral=True
        )

@bot.tree.command(
    name="경제복구",
    description="JSON으로 경제 데이터를 복구합니다."
)
@app_commands.describe(
    json_data="복구할 경제 데이터(JSON 형식)"
)
async def restore_economy(
    interaction: discord.Interaction,
    json_data: str, 
):
    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "관리자만 사용 가능합니다.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = json.loads(json_data)

        to_insert = [
            (
                user["user_id"],
                user["money"],
                user["last_daily"],
                user["exp"],
                user["level"]
            )
            for user in data
        ]

        cur.executemany(
            """
            INSERT OR REPLACE INTO economy(user_id,money,last_daily,exp,level)
            VALUES(?,?,?,?,?)
            """,
            to_insert
        )
        conn.commit()

        await interaction.followup.send(
            f"✅ 경제 복구 완료\n복구된 유저: {len(to_insert)}명"
        )

    except json.JSONDecodeError:
        await interaction.followup.send(
            "❌ JSON 형식이 올바르지 않습니다.",
            ephemeral=True
        )

    except Exception as e:
        await interaction.followup.send(
            f"복구 실패: {e}",
            ephemeral=True
        )

@bot.tree.command(name="경제백업", description="경제 데이터를 JSON으로 백업합니다.")
async def backup_economy(interaction: discord.Interaction):

    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용 가능", ephemeral=True)
        return

    try:

        cur.execute(
            "SELECT user_id, money, last_daily, exp, level FROM economy"
        )

        rows = cur.fetchall()

        data = []

        for row in rows:

            data.append({
                "user_id": row[0],
                "money": row[1],
                "last_daily": row[2],
                "exp": row[3],
                "level": row[4]
            })

        with open("economy_backup.json","w",encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        await interaction.response.send_message(
            f"💾 경제 데이터 백업 완료!\n유저 수: {len(data)}명"
        )

    except Exception as e:

        await interaction.response.send_message(
            f"백업 실패: {e}"
        )

@bot.tree.command(name="내순위", description="내 랭킹 위치 확인")
async def my_rank(interaction: discord.Interaction):

    cur.execute(
        "SELECT user_id FROM economy ORDER BY money DESC"
    )

    rows = cur.fetchall()

    rank = 1

    for row in rows:

        if row[0] == interaction.user.id:
            break

        rank += 1

    await interaction.response.send_message(
        f"🏆 당신의 돈 랭킹 : **{rank}위**"
    )

@bot.tree.command(name="내경제", description="내 경제 정보를 확인합니다.")
async def my_economy(interaction: discord.Interaction):

    user = get_user(interaction.user.id)

    money = user[1]
    exp = user[3]
    level = user[4]

    need = 50 + (level * 25)

    embed = discord.Embed(
        title=f"{interaction.user.name} 경제 정보",
        color=discord.Color.gold()
    )

    embed.add_field(name="💰 돈", value=f"{money}", inline=True)
    embed.add_field(name="⭐ 레벨", value=f"{level}", inline=True)
    embed.add_field(name="📊 EXP", value=f"{exp}/{need}", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)
@bot.tree.command(name="송금", description="다른 유저에게 돈을 송금합니다.")
@app_commands.describe(
    대상="돈을 보낼 유저",
    금액="보낼 금액 (정수)"
)
async def pay(
    interaction: discord.Interaction,
    대상: discord.Member,
    금액: int,
):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    보낸이 = interaction.user

    if guild is None:
        await interaction.followup.send("길드에서만 사용 가능합니다.", ephemeral=True)
        return

    if 대상.id == 보낸이.id:
        await interaction.followup.send("자기 자신에게는 송금할 수 없습니다.", ephemeral=True)
        return

    if 금액 <= 0:
        await interaction.followup.send("송금 금액은 1 이상이어야 합니다.", ephemeral=True)
        return
    sender_data = get_user(보낸이.id)
    sender_money = sender_data[1]

    if sender_money < 금액:
        await interaction.followup.send("잔액이 부족합니다.", ephemeral=True)
        return
    receiver_data = get_user(대상.id)
    receiver_money = receiver_data[1]
    new_sender_money = sender_money - 금액
    new_receiver_money = receiver_money + 금액

    cur.execute(
        "UPDATE economy SET money=? WHERE user_id=?",
        (new_sender_money, 보낸이.id),
    )
    cur.execute(
        "UPDATE economy SET money=? WHERE user_id=?",
        (new_receiver_money, 대상.id),
    )
    conn.commit()
    cursor.execute(
        """
        INSERT INTO transfer_logs(guild_id, from_id, to_id, amount, created_at)
        VALUES(?, ?, ?, ?, datetime('now'))
        """,
        (guild.id, 보낸이.id, 대상.id, 금액),
    )
    conn.commit()
    embed = discord.Embed(
        title="💸 송금 완료",
        color=discord.Color.green(),
        description=(
            f"{보낸이.mention} → {대상.mention}\n"
            f"`{금액}`원을 송금했습니다."
        ),
    )
    embed.add_field(name="내 잔액", value=f"`{new_sender_money}`", inline=True)
    embed.add_field(name="상대 잔액", value=f"`{new_receiver_money}`", inline=True)

    await interaction.followup.send(embed=embed, ephemeral=True)
    await send_admin_log(
        guild,
        title="💸 송금",
        description="유저 간 송금이 발생했습니다.",
        color=discord.Color.blurple(),
        fields=[
            ("보낸이", f"{보낸이.mention} (`{보낸이.id}`)", False),
            ("받는이", f"{대상.mention} (`{대상.id}`)", False),
            ("금액", f"`{금액}`", True),
            ("보낸이 잔액", f"`{new_sender_money}`", True),
            ("받는이 잔액", f"`{new_receiver_money}`", True),
        ],
    )
@bot.tree.command(name="랭킹", description="서버 경제 랭킹을 보여줍니다.")
@app_commands.describe(
    종류="랭킹 기준 (money, level, exp)"
)
@app_commands.choices(
    종류=[
        app_commands.Choice(name="돈", value="money"),
        app_commands.Choice(name="레벨", value="level"),
        app_commands.Choice(name="경험치", value="exp"),
    ]
)
async def ranking(
    interaction: discord.Interaction,
    종류: app_commands.Choice[str],
):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("길드에서만 사용 가능합니다.", ephemeral=True)
        return

    column = 종류.value
    cur.execute(
        f"""
        SELECT user_id, {column}
        FROM economy
        ORDER BY {column} DESC
        LIMIT 10
        """
    )
    rows = cur.fetchall()
    if not rows:
        await interaction.followup.send("랭킹 데이터가 없습니다.", ephemeral=True)
        return

    lines = []
    for idx, (user_id, value) in enumerate(rows, start=1):
        member = guild.get_member(user_id)
        name = member.display_name if member else f"`{user_id}`"
        lines.append(f"{idx}. {name} - `{value}`")

    title = {
        "money": "💰 돈 랭킹",
        "level": "⭐ 레벨 랭킹",
        "exp": "📊 경험치 랭킹",
    }[column]

    embed = discord.Embed(
        title=title,
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

BOT_STATUS = "정상"
STATUS_EMOJIS = {
    "정상": "🟢",
    "서비스 준비중": "🟡",
    "중지": "🔴"
}

SUPPORT_SERVER = "https://discord.gg/e3Mb5mdSAe"
bot_start_time = time.time()
status_channel_id = 1480268362889166989
status_msg = None

def generate_status_embed(title="🤖 봇 상태"):
    uptime = int(time.time() - bot_start_time)
    hours = uptime // 3600
    minutes = (uptime % 3600) // 60
    seconds = uptime % 60
    status_emoji = STATUS_EMOJIS.get(BOT_STATUS, "⚪")
    cpu_usage = psutil.cpu_percent(interval=None)
    memory_usage = psutil.virtual_memory().percent
    total_users = sum(g.member_count for g in bot.guilds)
    command_count = len(bot.commands)
    ping = round(bot.latency * 1000)

    embed = discord.Embed(title=title, color=discord.Color.green())
    embed.add_field(name="⏱ 업타임", value=f"{hours}시간 {minutes}분 {seconds}초", inline=False)
    embed.add_field(name="📡 봇 상태", value=f"{status_emoji} {BOT_STATUS}", inline=False)
    embed.add_field(name="🌍 서버 수", value=f"{len(bot.guilds)}개", inline=False)
    embed.add_field(name="👥 총 유저 수", value=f"{total_users}", inline=True)
    embed.add_field(name="📦 명령어 수", value=f"{command_count}", inline=True)
    embed.add_field(name="⚡ 핑", value=f"{ping}ms", inline=True)
    embed.add_field(name="🧠 메모리 사용량", value=f"{memory_usage}%", inline=True)
    embed.add_field(name="📊 CPU 사용량", value=f"{cpu_usage}%", inline=True)
    embed.add_field(name="🔗 서포트 서버", value=SUPPORT_SERVER, inline=False)
    return embed

@bot.tree.command(
    name="봇상태지정",
    description="봇 상태를 변경합니다 (관리자)"
)
@app_commands.describe(status="봇 상태 선택")
@app_commands.choices(status=[
    app_commands.Choice(name="정상", value="정상"),
    app_commands.Choice(name="서비스 준비중", value="서비스 준비중"),
    app_commands.Choice(name="중지", value="중지")
])
async def set_bot_status(interaction: Interaction, status: app_commands.Choice[str]):
    global BOT_STATUS
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    BOT_STATUS = status.value
    await interaction.response.send_message(
        f"봇 상태가 **{STATUS_EMOJIS[BOT_STATUS]} {BOT_STATUS}** 로 변경되었습니다.",
        ephemeral=True
    )

@bot.tree.command(
    name="봇정보",
    description="봇 정보를 확인합니다"
)
async def bot_info(interaction: Interaction):
    embed = generate_status_embed(title="🤖 봇 정보")
    embed.color = discord.Color.blue()
    embed.set_footer(text=f"요청자: {interaction.user}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(
    name="상태채널지정",
    description="봇 상태 자동 갱신 채널을 지정합니다 (관리자)"
)
@app_commands.describe(channel="봇 상태가 갱신될 채널")
async def set_status_channel(interaction: Interaction, channel: discord.TextChannel):
    global status_channel_id
    if not is_admin(interaction.user):
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    status_channel_id = channel.id
    await interaction.response.send_message(f"{channel.mention} 채널로 상태 갱신이 설정되었습니다.", ephemeral=True)

patch_channel_ids: list[int] = []
scheduled_patches: list[dict] = []

@bot.tree.command(
    name="패치채널지정",
    description="공지/패치 메시지를 보낼 채널 추가 (관리자)"
)
@app_commands.describe(channel="공지 메시지를 보낼 텍스트 채널")
async def add_patch_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    if channel.id not in patch_channel_ids:
        patch_channel_ids.append(channel.id)
        await interaction.response.send_message(
            f"{channel.mention} 채널이 패치 공지 채널에 추가되었습니다.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{channel.mention} 채널은 이미 목록에 있습니다.", ephemeral=True
        )

@bot.tree.command(
    name="패치예약",
    description="제작자 전용: 지정 시간에 패치 자동 전송"
)
@app_commands.describe(
    title="임베드 제목",
    content="임베드 내용",
    color="16진수 색상 (예: FF00AA)",
    image_url="상단에 표시될 이미지 URL",
    time="예약 시간 (YYYY-MM-DD HH:MM, 24시간제)"
)
async def schedule_patch(
    interaction: discord.Interaction,
    title: str,
    content: str,
    color: str,
    image_url: str,
    time: str
):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("제작자만 사용할 수 있습니다.", ephemeral=True)
        return

    try:
        schedule_time = datetime.strptime(time, "%Y-%m-%d %H:%M")
    except:
        await interaction.response.send_message("시간 형식이 잘못되었습니다. 예: 2026-03-09 21:30", ephemeral=True)
        return

    scheduled_patches.append({
        "time": schedule_time,
        "title": title,
        "content": content,
        "color": color,
        "image_url": image_url,
        "guild_id": interaction.guild.id
    })

    await interaction.response.send_message(f"패치가 {schedule_time}에 예약되었습니다.", ephemeral=True)
       
@bot.tree.command(name="도움말", description="서버에서 사용할 수 있는 명령어 목록을 보여줍니다.")
async def 도움말(interaction: discord.Interaction):
    view = HelpView(interaction.user)
    embed = view.make_page_embed()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
@app_commands.default_permissions(administrator=True)
@bot.tree.command(name="유저관리", description="특정 유저를 경고/제재/정보조회 등으로 관리합니다.")
@app_commands.describe(
    유저="관리할 유저",
    액션="info: 정보, warn: 경고 1회, resetwarn: 경고 초기화, kick/ban/timeout: 제재",
    시간="timeout 시간(분 단위, 예: 10)",
    사유="경고 또는 제재 사유"
)
@app_commands.choices(액션=[
    app_commands.Choice(name="정보 보기", value="info"),
    app_commands.Choice(name="경고 1회 추가", value="warn"),
    app_commands.Choice(name="경고 초기화", value="resetwarn"),
    app_commands.Choice(name="타임아웃", value="timeout"),
    app_commands.Choice(name="킥", value="kick"),
    app_commands.Choice(name="밴", value="ban"),
])
async def 유저관리(
    interaction: discord.Interaction,
    유저: discord.Member,
    액션: app_commands.Choice[str],
    시간: int | None = None,
    사유: str | None = None,
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    action = 액션.value

    if action == "info":
        await 유저정보.callback(interaction, 유저)  # type: ignore
        return

    if action == "warn":
        reason = 사유 or "관리자 수동 경고"
        cursor.execute(
            "SELECT warns FROM warnings WHERE guildid=? AND userid=?",
            (guild.id, 유저.id),
        )
        row = cursor.fetchone()
        currentwarns = row[0] if row else 0
        newwarns = currentwarns + 1
        cursor.execute(
            """
            INSERT INTO warnings (guildid, userid, warns)
            VALUES (?, ?, ?)
            ON CONFLICT(guildid, userid) DO UPDATE SET warns=excluded.warns
            """,
            (guild.id, 유저.id, newwarns),
        )
        cursor.execute(
            """
            INSERT INTO modlogs (guildid, userid, action, moderatorid, reason, createdat)
            VALUES (?, ?, 'warn', ?, ?, ?)
            """,
            (guild.id, 유저.id, interaction.user.id, reason, datetime.now().isoformat(sep=" ", timespec="seconds")),
        )
        conn.commit()
        await interaction.response.send_message(f"{유저.mention} 에게 경고 1회 부여 (총 {newwarns}회).", ephemeral=True)
        return

    if action == "resetwarn":
        cursor.execute(
            "DELETE FROM warnings WHERE guildid=? AND userid=?",
            (guild.id, 유저.id),
        )
        conn.commit()
        await interaction.response.send_message(f"{유저.mention} 의 경고를 초기화했습니다.", ephemeral=True)
        return

    # timeout / kick / ban
    reason = 사유 or "유저관리 명령으로 인한 조치"

    try:
        if action == "timeout":
            if 시간 is None or 시간 <= 0:
                await interaction.response.send_message("타임아웃 시간(분)을 1 이상으로 입력해야 합니다.", ephemeral=True)
                return

            duration_seconds = 시간 * 60
            until = discord.utils.utcnow() + discord.timedelta(seconds=duration_seconds)
            await 유저.timeout(until, reason=reason)
            action_name = f"타임아웃 {시간}분"

        elif action == "kick":
            await guild.kick(유저, reason=reason)
            action_name = "킥"

        else:  # ban
            await guild.ban(유저, reason=reason)
            action_name = "밴"

    except discord.Forbidden:
        await interaction.response.send_message("권한 부족으로 제재에 실패했습니다.", ephemeral=True)
        return
    except discord.HTTPException:
        await interaction.response.send_message("제재 처리 중 오류가 발생했습니다.", ephemeral=True)
        return

    # modlogs 기록
    cursor.execute(
        """
        INSERT INTO modlogs (guildid, userid, action, moderatorid, reason, createdat)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (guild.id, 유저.id, action, interaction.user.id, reason, datetime.now().isoformat(sep=" ", timespec="seconds")),
    )
    conn.commit()

    await interaction.response.send_message(f"{유저.mention} 을(를) {action_name} 처리했습니다.", ephemeral=True)
    
@bot.tree.command(name="서버정보", description="서버 기본 정보를 보여줍니다.")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    total_members = guild.member_count
    humans = len([m for m in guild.members if not m.bot])
    bots = total_members - humans

    text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])

    embed = discord.Embed(
        title=f"서버 정보 - {guild.name}",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="총 인원", value=f"{total_members}명 (사람 {humans}, 봇 {bots})", inline=False)
    embed.add_field(name="채널 수", value=f"텍스트 {text_channels}, 음성 {voice_channels}", inline=True)
    embed.add_field(name="역할 수", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="생성일", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.tree.command(name="핑", description="봇의 지연 시간을 확인합니다.")
async def ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000, 2)
    await interaction.response.send_message(f"현재 핑: **{latency_ms}ms**", ephemeral=True)
    
@bot.tree.command(name="유저정보", description="특정 유저의 정보와 상태를 확인합니다.")
async def userinfo(interaction: discord.Interaction, member: discord.Member | None = None):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    target = member or interaction.user

    # 경제
    cur.execute("SELECT money, level FROM economy WHERE user_id=?", (target.id,))
    row = cur.fetchone()
    money = row[0] if row else 0
    level = row[1] if row else 1

    # 경고
    cursor.execute(
        "SELECT warns FROM warnings WHERE guild_id=? AND user_id=?",
        (guild.id, target.id),
    )
    wrow = cursor.fetchone()
    warns = wrow[0] if wrow else 0

    # 인증
    cursor.execute(
        "SELECT verified, roblox_nick FROM users WHERE discord_id=? AND guild_id=?",
        (target.id, guild.id),
    )
    urow = cursor.fetchone()
    verified = bool(urow and urow[0])
    roblox_nick = urow[1] if urow else "등록 없음"

    roles = [r.mention for r in target.roles if r != guild.default_role]
    roles_text = ", ".join(roles) if roles else "역할 없음"

    embed = discord.Embed(
        title=f"{target} 유저 정보",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="가입일", value=target.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.add_field(name="경제", value=f"Money: {money}\nLevel: {level}", inline=False)
    embed.add_field(name="경고 수", value=str(warns), inline=True)
    embed.add_field(name="인증 상태", value="✅ 인증됨" if verified else "❌ 미인증", inline=True)
    embed.add_field(name="Roblox 닉네임", value=roblox_nick, inline=False)
    embed.add_field(name="역할", value=roles_text[:1024], inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@app_commands.default_permissions(manage_nicknames=True)
@bot.tree.command(name="닉변경", description="닉네임을 변경합니다. (다른 유저 변경은 관리자만)")
async def change_nick(
    interaction: discord.Interaction,
    new_nick: str,
    member: discord.Member | None = None,
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    caller = interaction.user
    target = member or caller  # 멤버가 없으면 본인

    # 다른 유저 닉네임 변경 시 권한 체크
    if target.id != caller.id:
        # 관리자/관리 닉네임 권한 없으면 거부
        if not (caller.guild_permissions.manage_nicknames or caller.guild_permissions.administrator):
            await interaction.response.send_message(
                "다른 유저의 닉네임은 관리자만 변경할 수 있습니다.",
                ephemeral=True,
            )
            return

    try:
        await target.edit(nick=new_nick)
        if target.id == caller.id:
            msg = f"닉네임이 **{new_nick}**(으)로 변경되었습니다."
        else:
            msg = f"{target.mention} 님의 닉네임을 **{new_nick}**(으)로 변경했습니다."

        await interaction.response.send_message(msg, ephemeral=True)

    except discord.Forbidden:
        await interaction.response.send_message(
            "닉네임을 변경할 권한이 없거나 역할 순서가 맞지 않습니다.",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.response.send_message(
            f"닉네임 변경 중 오류가 발생했습니다: {e}",
            ephemeral=True,
        )
                
@app_commands.default_permissions(manage_guild=True)
@bot.tree.command(name="서버공지", description="지정한 채널에 공지 임베드를 전송합니다.")
async def server_announce(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    제목: str,
    내용: str,
):
    embed = discord.Embed(
        title=f"📢 {제목}",
        description=내용,
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"작성자: {interaction.user}", icon_url=interaction.user.display_avatar.url)

    try:
        await channel.send(embed=embed)
        await interaction.response.send_message("공지 전송 완료!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"공지 전송 중 오류가 발생했습니다: {e}", ephemeral=True)

@bot.tree.command(name="일괄역할추가", description="여러 유저에게 한 번에 역할을 추가합니다. (관리자 전용)")
async def bulk_add_role(
    interaction: discord.Interaction,
    role: discord.Role,
    봇포함: bool = False,
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    # 실행자 관리자 확인
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
        return

    if role >= guild.me.top_role:
        await interaction.response.send_message("이 역할은 제가 관리할 수 없습니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    count = 0
    for member in guild.members:
        if not 봇포함 and member.bot:
            continue
        if role in member.roles:
            continue
        try:
            await member.add_roles(role, reason=f"/일괄역할추가 by {interaction.user}")
            count += 1
        except discord.Forbidden:
            continue
        except Exception:
            continue

    await interaction.followup.send(f"{count}명에게 {role.mention} 역할을 추가했습니다.", ephemeral=True)

@bot.tree.command(name="일괄역할삭제", description="여러 유저에게서 한 번에 역할을 제거합니다. (관리자 전용)")
async def bulk_remove_role(
    interaction: discord.Interaction,
    role: discord.Role,
    봇포함: bool = False,
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
        return

    if role >= guild.me.top_role:
        await interaction.response.send_message("이 역할은 제가 관리할 수 없습니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    count = 0
    for member in guild.members:
        if not 봇포함 and member.bot:
            continue
        if role not in member.roles:
            continue
        try:
            await member.remove_roles(role, reason=f"/일괄역할삭제 by {interaction.user}")
            count += 1
        except discord.Forbidden:
            continue
        except Exception:
            continue

    await interaction.followup.send(f"{count}명에게서 {role.mention} 역할을 제거했습니다.", ephemeral=True)
    
@bot.tree.command(name="역할삭제", description="서버에서 특정 역할 자체를 삭제합니다. (관리자 전용)")
async def delete_role(
    interaction: discord.Interaction,
    role: discord.Role,
    확인: bool = False,
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
        return

    if not 확인:
        await interaction.response.send_message(
            f"{role.mention} 역할을 삭제하려면 `확인` 옵션을 **True**로 설정해 주세요.",
            ephemeral=True,
        )
        return

    if role >= guild.me.top_role:
        await interaction.response.send_message("이 역할은 제가 삭제할 수 없습니다.", ephemeral=True)
        return

    try:
        name = role.name
        await role.delete(reason=f"/역할삭제 by {interaction.user}")
        await interaction.response.send_message(f"역할 **{name}** 을(를) 삭제했습니다.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("역할을 삭제할 권한이 없습니다.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"역할 삭제 중 오류가 발생했습니다: {e}", ephemeral=True)
        
@bot.tree.command(name="역할지급", description="유저에게 역할을 추가하거나 제거합니다. (관리자 전용)")
async def give_role(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role,
    add: bool = True,
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    # 실행자 관리자 확인
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
        return

    # 봇이 관리할 수 있는 역할인지 확인
    if role >= guild.me.top_role:
        await interaction.response.send_message("이 역할은 제가 관리할 수 없습니다.", ephemeral=True)
        return

    try:
        if add:
            await member.add_roles(role, reason=f"/역할지급 by {interaction.user}")
            msg = f"{member.mention} 에게 {role.mention} 역할을 부여했습니다."
        else:
            await member.remove_roles(role, reason=f"/역할지급 제거 by {interaction.user}")
            msg = f"{member.mention} 에서 {role.mention} 역할을 제거했습니다."

        await interaction.response.send_message(msg, ephemeral=True)

    except discord.Forbidden:
        await interaction.response.send_message("역할을 변경할 권한이 없습니다.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"역할 변경 중 오류가 발생했습니다: {e}", ephemeral=True)

@bot.tree.command(name="아바타", description="유저의 프로필 이미지를 크게 보여줍니다.")
async def avatar(
    interaction: discord.Interaction,
    member: discord.Member | None = None,
):
    target = member or interaction.user
    embed = discord.Embed(
        title=f"{target} 의 아바타",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)
    
@bot.tree.command(name="현재시간", description="현재 시간을 여러 형태로 보여줍니다.")
async def servertime(interaction: discord.Interaction):
    now_utc = datetime.now(timezone.utc)
    kst = timezone(timedelta(hours=9))
    now_kst = now_utc.astimezone(kst)

    embed = discord.Embed(
        title="⏰ 현재 시각",
        color=discord.Color.blurple(),
        timestamp=now_utc,
    )
    embed.add_field(name="UTC", value=now_utc.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.add_field(name="KST (UTC+9)", value=now_kst.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.tree.command(name="서버핑", description="봇의 지연 시간을 상세히 확인합니다.")
async def server_ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000, 2)

    embed = discord.Embed(
        title="📡 봇 상태",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="웹소켓 핑", value=f"{latency_ms}ms", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.tree.command(name="내아이디", description="내 디스코드 ID를 확인합니다.")
async def my_id(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"{interaction.user.mention} 님의 ID: `{interaction.user.id}`",
        ephemeral=True,
    )

@bot.tree.command(name="유저아이디", description="내 아이디 또는 지정한 유저의 디스코드 ID를 확인합니다.")
async def id_command(
    interaction: discord.Interaction,
    member: discord.Member | None = None,
):
    target = member or interaction.user
    await interaction.response.send_message(
        f"{target.mention} 님의 ID: `{target.id}`",
        ephemeral=True,
    )
    
@bot.tree.command(name="서버이모지", description="서버의 커스텀 이모지를 목록으로 보여줍니다.")
async def server_emojis(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    if not guild.emojis:
        await interaction.response.send_message("등록된 커스텀 이모지가 없습니다.", ephemeral=True)
        return

    lines = []
    for e in guild.emojis:
        lines.append(f"{e}  `:{e.name}:`  (`{e.id}`)")
    desc = "\n".join(lines[:50])  # 너무 많으면 50개까지만

    embed = discord.Embed(
        title=f"{guild.name} 이모지 목록",
        description=desc,
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.tree.command(name="링크보기", description="서버 초대 링크 목록을 확인합니다.")
async def list_invites(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    try:
        invites = await guild.invites()
    except discord.Forbidden:
        await interaction.response.send_message("초대 링크를 볼 권한이 없습니다.", ephemeral=True)
        return
    except Exception as e:
        await interaction.response.send_message(f"초대 링크 조회 중 오류가 발생했습니다: {e}", ephemeral=True)
        return

    if not invites:
        await interaction.response.send_message("현재 유효한 초대 링크가 없습니다.", ephemeral=True)
        return

    lines = []
    for inv in invites[:20]:  # 너무 많으면 20개까지만
        creator = inv.inviter.mention if inv.inviter else "알 수 없음"
        uses = inv.uses or 0
        max_uses = inv.max_uses or "무제한"
        max_age = inv.max_age or 0
        if max_age == 0:
            expire_text = "만료 없음"
        else:
            expire_text = f"{max_age // 60}분"

        lines.append(
            f"[{inv.code}] {inv.url}\n"
            f"→ 생성자: {creator}, 사용: {uses}/{max_uses}, 만료: {expire_text}"
        )

    desc = "\n\n".join(lines)

    embed = discord.Embed(
        title="📎 서버 초대 링크 목록",
        description=desc[:4096],
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.tree.command(name="서버통계", description="서버 인원 통계를 간단히 보여줍니다.")
async def server_stats(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    total = guild.member_count
    humans = len([m for m in guild.members if not m.bot])
    bots = total - humans
    human_pct = round(humans / total * 100, 1) if total else 0
    bot_pct = round(bots / total * 100, 1) if total else 0

    embed = discord.Embed(
        title=f"{guild.name} 인원 통계",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="총 인원", value=f"{total}명", inline=True)
    embed.add_field(name="사람", value=f"{humans}명 ({human_pct}%)", inline=True)
    embed.add_field(name="봇", value=f"{bots}명 ({bot_pct}%)", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.tree.command(name="서버생성일", description="이 서버의 생성일을 확인합니다.")
async def server_created(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    created = guild.created_at.replace(tzinfo=timezone.utc)
    kst = timezone(timedelta(hours=9))
    created_kst = created.astimezone(kst)

    embed = discord.Embed(
        title=f"{guild.name} 서버 생성일",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="UTC", value=created.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.add_field(name="KST (UTC+9)", value=created_kst.strftime("%Y-%m-%d %H:%M:%S"), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.tree.command(name="서버가입정보", description="이 서버에 내가 언제 들어왔는지 확인합니다.")
async def my_join_date(interaction: discord.Interaction):
    member = interaction.user
    guild = interaction.guild
    if guild is None or member.joined_at is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    joined = member.joined_at.replace(tzinfo=timezone.utc)
    kst = timezone(timedelta(hours=9))
    joined_kst = joined.astimezone(kst)

    embed = discord.Embed(
        title=f"{member.display_name} 님의 서버 가입일",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="UTC", value=joined.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.add_field(name="KST (UTC+9)", value=joined_kst.strftime("%Y-%m-%d %H:%M:%S"), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.tree.command(name="내역할", description="내가 가지고 있는 역할 목록을 보여줍니다.")
async def my_roles(interaction: discord.Interaction):
    guild = interaction.guild
    member = interaction.user
    if guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능합니다.", ephemeral=True)
        return

    roles = [r.mention for r in member.roles if r != guild.default_role]
    text = ", ".join(roles) if roles else "역할이 없습니다."

    embed = discord.Embed(
        title=f"{member.display_name} 님의 역할",
        description=text[:4096],
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    

async def send_patch_embed(guild: discord.Guild, embed: discord.Embed):
    sent_users = set()
    success, fail = 0, 0
    for member in guild.members:
        if member.bot or member.id in sent_users:
            continue
        try:
            await member.send(embed=embed)
            sent_users.add(member.id)
            success += 1
            await asyncio.sleep(1)
        except:
            fail += 1
    unique_channels = list(set(patch_channel_ids))
    for cid in unique_channels:
        channel = bot.get_channel(cid)
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass

    print(f"[패치 전송 완료] DM 성공: {success}, 실패: {fail}, 채널 전송: {len(unique_channels)}개")

@tasks.loop(seconds=60)
async def patch_scheduler_loop():
    now = datetime.now()
    for patch_info in scheduled_patches[:]:
        if now >= patch_info["time"]:
            guild = bot.get_guild(patch_info["guild_id"])
            if guild:
                try:
                    embed_color = int(patch_info["color"], 16)
                except:
                    embed_color = 0x00FF00
                embed = discord.Embed(
                    title=patch_info["title"],
                    description=patch_info["content"],
                    color=embed_color
                )
                if patch_info["image_url"]:
                    embed.set_image(url=patch_info["image_url"])

                await send_patch_embed(guild, embed)
            scheduled_patches.remove(patch_info)

@tasks.loop(seconds=5)
async def update_status():
    global status_msg
    if not status_channel_id:
        return

    channel = bot.get_channel(status_channel_id)
    if not channel:
        return
    if not patch_scheduler_loop.is_running():
        patch_scheduler_loop.start()
    embed = generate_status_embed(title="🤖 봇 상태 (자동 갱신)")
    if status_msg is None:
        try:
            status_msg = await channel.send(embed=embed)
        except discord.Forbidden:
            return
        except discord.HTTPException:
            return
        return
    try:
        await status_msg.edit(embed=embed)
    except discord.NotFound:
        try:
            status_msg = await channel.send(embed=embed)
        except:
            pass
    except discord.HTTPException:
        pass

@app.get("/api/bot-stats")
def bot_stats():
    """Bot 통계"""
    try:
        guilds_count = len(bot.guilds)
        return {
            "guilds": guilds_count,
            "verified_users": guilds_count * 10,
            "warn_records": 0,
        }
    except Exception as e:
        print(f"Bot stats error: {e}")
        return {"guilds": 0, "verified_users": 0, "warn_records": 0}
    
ALLOWED_GUILD_IDS = [
    1461636782176075830,
    1479791881046065286
    ]
SECURITY_LOG_CHANNEL_ID = 1468191965052141629
DEVELOPER_ID = 1276176866440642561 

KST = timezone(timedelta(hours=9)) 

@tasks.loop(hours=6)
async def sync_all_nicknames_task():
    """6시간마다 전체 유저의 Roblox 정보를 동기화하고 닉네임 업데이트"""
    try:
        cursor.execute("SELECT guild_id FROM rank_log_settings WHERE enabled=1")
        settings = cursor.fetchall() 

        for (guild_id,) in settings:
            guild = bot.get_guild(guild_id)
            if not guild:
                continue 

            cursor.execute(
                "SELECT discord_id, roblox_nick FROM users WHERE guild_id=? AND verified=1",
                (guild_id,),
            )
            users = cursor.fetchall() 

            if not users:
                continue 

            usernames = [u[1] for u in users]

            BATCH_SIZE = 100
            for i in range(0, len(usernames), BATCH_SIZE):
                batch = usernames[i:i + BATCH_SIZE]
                
                try:
                    resp = requests.post(
                        f"{RANK_API_URL_ROOT}/bulk-status",
                        json={"usernames": batch},
                        headers=_rank_api_headers(),
                        timeout=30,
                    ) 

                    if resp.status_code == 200:
                        data = resp.json()
                        
                        for r in data.get("results", []):
                            if r.get("success"):
                                username = r['username']
                                role_info = r.get("role", {})
                                rank_name = role_info.get("name", "?")
                                for discord_id, roblox_nick in users:
                                    if roblox_nick == username:
                                        member = guild.get_member(discord_id)
                                        if member:
                                            try:
                                                new_nick = f"[{rank_name}] {username}"
                                                if len(new_nick) > 32:
                                                    new_nick = new_nick[:32]
                                                if member.nick != new_nick:
                                                    await member.edit(nick=new_nick)
                                            except Exception as e:
                                                print(f"닉네임 변경 실패 {username}: {e}")
                                        break
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"Batch {i} sync error: {e}")
                    continue 

        print(f"[{datetime.now()}] 전체 닉네임 동기화 완료")
        
    except Exception as e:
        print(f"sync_all_nicknames_task error: {e}")

@sync_all_nicknames_task.before_loop
async def before_sync_all_nicknames_task():
    await bot.wait_until_ready()
    
@tasks.loop(minutes=AUTO_BACKUP_MINUTES)
async def auto_backup_loop():
    for guild in bot.guilds:
        try:
            save_backup_data(guild)
            print(f"[자동백업 완료] {guild.name} ({guild.id})")
        except Exception as e:
            print(f"[자동백업 실패] {guild.name} ({guild.id}) -> {e}")


@auto_backup_loop.before_loop
async def before_auto_backup_loop():
    await bot.wait_until_ready()

@bot.event
async def on_member_join(member: discord.Member):
    data = load_backup_data(member.guild.id)
    if not data:
        return

    role_names = data.get("member_roles", {}).get(str(member.id), [])
    if not role_names:
        return

    roles_to_add = []
    for role_name in role_names:
        role = discord.utils.get(member.guild.roles, name=role_name)
        if role and not role.managed:
            try:
                if member.guild.me and role < member.guild.me.top_role:
                    roles_to_add.append(role)
            except Exception:
                pass

    if not roles_to_add:
        return

    try:
        await member.add_roles(*roles_to_add, reason="자동 역할 복구")
        print(f"[자동복구] {member} -> {[r.name for r in roles_to_add]}")
    except Exception as e:
        print(f"[자동복구 실패] {member} -> {e}")
    
@tasks.loop(seconds=5)
async def rank_log_task():
    """5분마다 그룹 가입자들의 랭크를 로그"""
    try:
        cursor.execute("SELECT guild_id, channel_id FROM rank_log_settings WHERE enabled=1")
        settings = cursor.fetchall() 

        for guild_id, channel_id in settings:
            guild = bot.get_guild(guild_id)
            if not guild:
                continue 

            channel = guild.get_channel(channel_id)
            if not channel:
                continue 

            try:
                cursor.execute(
                    "SELECT roblox_nick FROM users WHERE guild_id=? AND verified=1",
                    (guild_id,),
                )
                users = cursor.fetchall() 

                if not users:
                    continue 

                usernames = [u[0] for u in users]
                
                try:
                    resp = requests.post(
                        f"{RANK_API_URL_ROOT}/bulk-status",
                        json={"usernames": usernames},
                        headers=_rank_api_headers(),
                        timeout=30,
                    ) 

                    if resp.status_code == 200:
                        data = resp.json()
                        current_state = {}
                        for r in data.get("results", []):
                            if r.get("success"):
                                role_info = r.get("role", {})
                                current_state[r['username']] = {
                                    "rank": role_info.get('rank', 0),
                                    "rank_name": role_info.get('name', '?')
                                }
                        cursor.execute(
                            "SELECT id, log_data FROM rank_log_history WHERE guild_id=? ORDER BY id DESC LIMIT 1",
                            (guild_id,),
                        )
                        prev_row = cursor.fetchone() 

                        changes = []
                        if prev_row:
                            prev_id, prev_log = prev_row
                            prev_data = json.loads(prev_log)
                            prev_state = {item["username"]: item for item in prev_data} 
                            for username, current in current_state.items():
                                if username in prev_state:
                                    prev = prev_state[username]
                                    if prev["rank"] != current["rank"]:
                                        changes.append({
                                            "username": username,
                                            "old_rank": prev["rank"],
                                            "old_rank_name": prev["rank_name"],
                                            "new_rank": current["rank"],
                                            "new_rank_name": current["rank_name"]
                                        }) 
                        if changes:
                            cursor.execute(
                                "SELECT auto_rollback FROM rollback_settings WHERE guild_id=?",
                                (guild_id,),
                            )
                            rollback_row = cursor.fetchone()
                            auto_rollback = rollback_row[0] if rollback_row else 1 

                            if len(changes) >= 10 and auto_rollback == 1:
                                try:
                                    rollback_results = []
                                    for change in changes:
                                        resp_rollback = requests.post(
                                            f"{RANK_API_URL_ROOT}/rank",
                                            json={
                                                "username": change["username"],
                                                "rank": change["old_rank"]
                                            },
                                            headers=_rank_api_headers(),
                                            timeout=15,
                                        )
                                        if resp_rollback.status_code == 200:
                                            rollback_results.append(f"{change['username']}")
                                        else:
                                            rollback_results.append(f"{change['username']}") 
                                    embed = discord.Embed(
                                        title="자동 롤백 실행",
                                        description=f"5분 내 {len(changes)}명 변경 감지 → 자동 롤백",
                                        color=discord.Color.red(),
                                        timestamp=datetime.now(timezone.utc),
                                    )
                                    embed.add_field(
                                        name="롤백 결과",
                                        value="\n".join(rollback_results[:20]),
                                        inline=False
                                    )
                                    await channel.send(embed=embed)
                                    continue 

                                except Exception as e:
                                    print(f"Auto rollback error: {e}") 
                            log_data = [{"username": k, **v} for k, v in current_state.items()]
                            cursor.execute(
                                "INSERT INTO rank_log_history(guild_id, log_data, created_at) VALUES(?, ?, ?)",
                                (guild_id, json.dumps(log_data), datetime.now().isoformat()),
                            )
                            conn.commit()
                            
                            cursor.execute(
                                "SELECT id FROM rank_log_history WHERE guild_id=? ORDER BY id DESC LIMIT 1",
                                (guild_id,),
                            )
                            log_id = cursor.fetchone()[0]
                            change_lines = []
                            for c in changes:
                                change_lines.append(
                                    f"{c['username']}: {c['old_rank_name']}(rank {c['old_rank']}) → {c['new_rank_name']}(rank {c['new_rank']})"
                                )
                            
                            msg = "\n".join(change_lines)
                            embed = discord.Embed(
                                title="명단 변경 로그",
                                description=msg[:2000],
                                color=discord.Color.orange(),
                                timestamp=datetime.now(timezone.utc),
                            )
                            embed.set_footer(text=f"일련번호: {log_id} | 변경: {len(changes)}건")
                            await channel.send(embed=embed) 

                except Exception as e:
                    print(f"rank_log_task API error: {e}") 

            except Exception as e:
                print(f"rank_log_task error for guild {guild_id}: {e}") 

    except Exception as e:
        print(f"rank_log_task error: {e}")


@rank_log_task.before_loop
async def before_rank_log_task():
    await bot.wait_until_ready() 

@bot.event
async def on_guild_join(guild: discord.Guild):
    now_kst = datetime.now(KST)
    if guild.id in ALLOWED_GUILD_IDS:
        dev = await bot.fetch_user(DEVELOPER_ID)
        embed = discord.Embed(
            title="✅ 허용 서버 연결",
            description=(
                f"서버 이름: {guild.name}\n"
                f"서버 ID: {guild.id}\n"
                f"인원수: {guild.member_count}"
            ),
            color=discord.Color.green(),
            timestamp=now_kst
        )
        await dev.send(embed=embed)
        return
    await guild.chunk()
    shared_members: list[discord.Member] = []

    for allowed_id in ALLOWED_GUILD_IDS:
        allowed_guild = bot.get_guild(allowed_id)
        if not allowed_guild:
            continue

        await allowed_guild.chunk()

        allowed_ids = {m.id for m in allowed_guild.members}
        for member in guild.members:
            if member.id in allowed_ids:
                shared_members.append(member)
    for member in shared_members:
        try:
            user = await bot.fetch_user(member.id)
            await user.send(
                f"⚠️ 경고: 당신은 허용되지 않은 서버 '{guild.name}'에 있습니다.\n"
                "보안 시스템에 의해 기록되었습니다."
            )
        except:
            pass
    member_lines = [f"{m} ({m.id})" for m in guild.members]
    buffer = io.BytesIO("\n".join(member_lines).encode("utf-8"))
    member_file = discord.File(buffer, filename=f"{guild.id}_members.txt")

    owner = guild.owner
    owner_text = f"{owner} ({owner.id})" if owner else "알 수 없음"
    created_text = guild.created_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")

    log_channel = bot.get_channel(SECURITY_LOG_CHANNEL_ID)

    if log_channel:
        embed = discord.Embed(
            title="🚨 비허용 서버 감지",
            description=(
                f"서버 이름: {guild.name}\n"
                f"서버 ID: {guild.id}\n"
                f"인원수: {guild.member_count}\n"
                f"서버 주인: {owner_text}\n"
                f"생성일(KST): {created_text}\n"
                f"교집합 인원: {len(shared_members)}명\n\n"
                "봇이 즉시 서버를 떠납니다."
            ),
            color=discord.Color.red(),
            timestamp=now_kst
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await log_channel.send(embed=embed, file=member_file)
    await guild.leave()
async def force_leave(guild: discord.Guild) -> None:
    """허가되지 않은 길드에서 나가고 로그 남김."""
    try:
        print(f"[FORCE_LEAVE] Leaving unauthorized guild: {guild.name} ({guild.id})")
        await guild.leave()
    except Exception as e:
        print(f"[FORCE_LEAVE] Failed to leave guild {guild.id}: {e}") 

status_channel_id = 1480268362889166989
status_message_id = 1480476381535273092

@tasks.loop(seconds=15)
async def update_status_loop():
    global status_message_id
    if not status_channel_id:
        print("상태 채널 미지정")
        return

    channel = bot.get_channel(status_channel_id)
    if not channel:
        print("채널을 찾을 수 없음")
        return
    uptime = int(time.time() - bot_start_time)
    hours = uptime // 3600
    minutes = (uptime % 3600) // 60
    seconds = uptime % 60
    status_emoji = STATUS_EMOJIS.get(BOT_STATUS, "⚪")

    cpu_usage = psutil.cpu_percent(interval=0.5)
    memory_usage = psutil.virtual_memory().percent
    total_users = sum(g.member_count for g in bot.guilds)
    ping = round(bot.latency * 1000)

    embed = discord.Embed(title="🤖 봇 상태 (자동 갱신)", color=discord.Color.green())
    embed.add_field(name="⏱ 업타임", value=f"{hours}시간 {minutes}분 {seconds}초", inline=False)
    embed.add_field(name="📡 봇 상태", value=f"{status_emoji} {BOT_STATUS}", inline=False)
    embed.add_field(name="🌍 서버 수", value=f"{len(bot.guilds)}개", inline=False)
    embed.add_field(name="👥 총 유저 수", value=f"{total_users}", inline=True)
    embed.add_field(name="⚡ 핑", value=f"{ping}ms", inline=True)
    embed.add_field(name="🧠 메모리 사용량", value=f"{memory_usage}%", inline=True)
    embed.add_field(name="📊 CPU 사용량", value=f"{cpu_usage}%", inline=True)
    embed.add_field(
        name="📦 명령어 수",
        value=f"34",
        inline=False
    )

    try:
        if status_message_id:
            msg = await channel.fetch_message(status_message_id)
            await msg.edit(embed=embed)
        else:
            msg = await channel.send(embed=embed)
            status_message_id = msg.id
    except Exception as e:
        print(f"상태 전송/수정 실패: {e}")
    
@bot.event
async def on_app_command_completion(
    interaction: discord.Interaction,
    command: discord.app_commands.Command,
):
    try:
        if not interaction.guild:
            return

        guild_id = interaction.guild.id
        user = interaction.user
        options = []
        if interaction.namespace:
            for k, v in interaction.namespace.__dict__.items():
                options.append(f"{k}={v}")
        full_str = f"/{command.qualified_name}"
        if options:
            full_str += " " + " ".join(options)

        cursor.execute(
            """
            INSERT INTO command_logs(
                guild_id, user_id, user_name,
                command_name, command_full, created_at
            )
            VALUES(?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                guild_id,
                user.id,
                f"{user.name}{user.discriminator}",
                command.qualified_name,
                full_str,
            ),
        )
        conn.commit()
    except Exception as e:
        add_error_log(f"command_log: {repr(e)}")

next_update = None

@tasks.loop(minutes=5)
async def update_chat_rate():

    global next_update

    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    next_update = now + datetime.timedelta(minutes=5)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    for guild in bot.guilds:
        if guild.id not in ALLOWED_GUILD_IDS:
            await force_leave(guild)
    try:
        if GUILD_ID > 0:
            await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync()
    except Exception as e:
        print("동기화 실패:", e)
    if not rank_log_task.is_running():
        rank_log_task.start()
    if not sync_all_nicknames_task.is_running():
        sync_all_nicknames_task.start()
    if not update_status.is_running():
        update_status.start()
        p
if __name__ == "__main__":    
    async def run_both():
        config = Config()
        config.bind = [f"0.0.0.0:{int(os.getenv('PORT', 8080))}"]
        
        await asyncio.gather(
            bot.start(TOKEN),
            serve(app, config)
        )
    
    asyncio.run(run_both())
