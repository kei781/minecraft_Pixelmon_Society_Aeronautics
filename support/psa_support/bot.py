from __future__ import annotations
import asyncio
import json
import logging
import time
import discord
from discord.ext import tasks
from .ai import Advisor
from .config import Config
from .knowledge import Knowledge
from .store import Store
from .codex_client import CodexClient

log = logging.getLogger("psa_support")


class SupportBot(discord.Client):
    def __init__(self, config: Config, advisor=None):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none(), max_messages=None)
        self.config = config
        self.knowledge = Knowledge(config.knowledge)
        self.store = Store(config.database)
        self.store.bind(config)
        self.advisor = advisor or Advisor(config.model, self.knowledge, CodexClient(config.codex_bin,config.codex_home,config.database.parent/"codex-work"))
        self.delivery_lock = asyncio.Lock()

    async def setup_hook(self):
        self.store.recover_processing()
        self.deliver.start()

    async def close(self):
        self.deliver.cancel()
        await super().close()

    async def on_ready(self):
        channel = self.get_channel(self.config.channel_id)
        if (not isinstance(channel, discord.TextChannel)
                or channel.guild.id != self.config.guild_id):
            log.error("Configured support channel is unavailable; stopping")
            await self.close()
            return
        permissions = channel.permissions_for(channel.guild.me)
        if not (permissions.view_channel and permissions.send_messages and permissions.read_message_history):
            log.error("Missing channel view/send/history permission; stopping")
            await self.close()
            return
        log.info("Connected; exact channel allowlist active")

    async def on_message(self, message):
        cfg = self.config
        if not cfg.accepts(getattr(message.guild, "id", None), message.channel.id,
                           bot=message.author.bot, webhook=bool(message.webhook_id)):
            return  # Must precede content access, history, persistence, and AI calls.
        question = message.content.strip()
        if not question:
            if message.attachments:
                await message.reply("증상을 글로 함께 적어 주세요. 현재는 첨부파일 내용을 자동으로 읽지 않습니다.", mention_author=False)
            return
        if len(question) > 3000:
            await message.reply("증상과 재현 순서를 3,000자 이내로 적어 주세요.", mention_author=False)
            return
        now = time.time()
        result = self.store.reserve(cfg, str(message.id), str(message.author.id), question, now)
        if result == "duplicate":
            return
        if result != "accepted":
            notices = {"cooldown":"잠시 뒤에 이어서 문의해 주세요.",
                       "daily_limit":"오늘의 자동 문의 처리 한도에 도달했습니다. 운영자에게 문의해 주세요.",
                       "busy":"다른 문의를 확인 중입니다. 잠시 뒤에 다시 보내 주세요."}
            await message.reply(notices[result], mention_author=False)
            return
        try:
            async with message.channel.typing():
                reference = getattr(message, 'reference', None)
                related_ticket = self.store.ticket_for_reply(str(reference.message_id), str(message.author.id)) if reference and reference.channel_id == cfg.channel_id else None
                history = self.store.ticket_context(related_ticket,str(message.author.id)) if related_ticket else self.store.history(str(message.author.id), now)
                decision = await asyncio.wait_for(self.advisor.answer(question, history), timeout=330)
                labels = [f"{self.knowledge.documents[s]['path']}:{self.knowledge.documents[s]['line']}"
                          for s in decision.source_ids]
                self.store.finish(str(message.id), decision, self.knowledge.manifest['snapshot_id'], labels,related_ticket)
        except Exception as exc:
            self.store.fail(str(message.id))
            # No raw questions, exception bodies, credentials, or player data in service logs.
            log.warning("Inquiry processing failed: %s", type(exc).__name__)
            await message.reply("자료 확인 중 오류가 발생했습니다. 답변이나 티켓 접수가 완료되지 않았습니다. 잠시 뒤 다시 문의해 주세요.", mention_author=False)
            return
        await self.flush()

    async def flush(self):
        async with self.delivery_lock:
            channel = self.get_channel(self.config.channel_id)
            if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.config.guild_id:
                return
            for row in self.store.pending():
                if not self.config.accepts(int(row['guild']), int(row['channel'])):
                    continue  # Never redirect an old installation's replies into a new channel.
                parts = json.loads(row['parts'])
                for part in parts[row['sent_parts']:]:
                    try:
                        sent = await channel.send(part, reference=discord.MessageReference(
                            message_id=int(row['id']), channel_id=channel.id,
                            guild_id=channel.guild.id, fail_if_not_exists=False),
                            allowed_mentions=discord.AllowedMentions.none())
                    except discord.HTTPException:
                        break  # Persisted outbox is retried by the periodic task.
                    if row['ticket'] is not None:
                        self.store.link_reply(str(sent.id),row['ticket'],row['author'])
                    self.store.sent_part(row['id'])
            labels = {'investigating':'조사 중', 'needs_information':'추가 정보 필요',
                      'resolved':'해결', 'not_a_bug':'버그 아님'}
            for update in self.store.notifications():
                # Notification text is written by the authenticated local operator CLI, never the model.
                text = f"**PSA-{update['ticket']:04d} · {labels[update['status']]}**\n{update['summary']}"
                if update['status']=='needs_information':
                    text += '\n\n추가 정보는 이 메시지에 답장해 주세요. 기존 티켓에 이어서 기록합니다.'
                try:
                    sent = await channel.send(text[:1800], reference=discord.MessageReference(
                        message_id=int(update['report_message']),channel_id=channel.id,
                        guild_id=channel.guild.id,fail_if_not_exists=False),
                        allowed_mentions=discord.AllowedMentions.none())
                except discord.HTTPException:
                    break
                self.store.link_reply(str(sent.id),update['ticket'],update['report_author'])
                self.store.notified(update['id'])

    @tasks.loop(seconds=15)
    async def deliver(self):
        try:
            await self.flush()
        except Exception as exc:
            log.warning("Outbox retry failed: %s", type(exc).__name__)

    @deliver.before_loop
    async def before_delivery(self):
        await self.wait_until_ready()
