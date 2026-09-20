import os
import time
from collections import defaultdict, deque

import telebot
from telebot import types
from telebot.types import ChatPermissions
from flask import Flask, request


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing.")

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)

app = Flask(__name__)


# ============================================================
# DATABASE
# ============================================================

warnings_db = defaultdict(
    lambda: defaultdict(int)
)

spam_tracker = defaultdict(
    lambda: deque(maxlen=10)
)

mute_tracker = {}


# ============================================================
# SETTINGS
# ============================================================

MAX_WARNINGS = 3

SPAM_MESSAGE_LIMIT = 7

SPAM_WINDOW = 10

DEFAULT_MUTE_SECONDS = 300


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def is_group(message):
    return message.chat.type in [
        "group",
        "supergroup"
    ]


def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(
            chat_id,
            user_id
        )

        return member.status in [
            "administrator",
            "creator"
        ]

    except Exception:
        return False


def is_owner(chat_id, user_id):
    try:
        member = bot.get_chat_member(
            chat_id,
            user_id
        )

        return member.status == "creator"

    except Exception:
        return False


def get_target_user(message):

    # --------------------------------------------------------
    # METHOD 1: REPLY TO MESSAGE
    # --------------------------------------------------------

    if message.reply_to_message:
        return message.reply_to_message.from_user

    # --------------------------------------------------------
    # METHOD 2: USERNAME / ID
    # --------------------------------------------------------

    if not message.text:
        return None

    parts = message.text.split()

    if len(parts) < 2:
        return None

    target = parts[1]

    # --------------------------------------------------------
    # TELEGRAM USER ID
    # --------------------------------------------------------

    if target.lstrip("-").isdigit():

        try:

            user_id = int(target)

            member = bot.get_chat_member(
                message.chat.id,
                user_id
            )

            return member.user

        except Exception:
            return None

    # --------------------------------------------------------
    # USERNAME
    # --------------------------------------------------------

    if target.startswith("@"):

        username = target[1:]

        try:

            # Telegram's get_chat_member normally expects
            # a numeric user ID, so username lookup is not
            # guaranteed by the Bot API.
            #
            # Therefore we return None here and recommend
            # replying to the user's message.

            return None

        except Exception:
            return None

    return None


def get_target_from_reply_or_command(message):

    user = get_target_user(message)

    if not user:

        bot.reply_to(
            message,
            "❌ <b>User not found.</b>\n\n"
            "Reply to the user's message and use the command.\n\n"
            "Example:\n"
            "<code>/ban</code>"
        )

    return user


def admin_required(message):

    if not is_group(message):

        bot.reply_to(
            message,
            "❌ This command can only be used inside a group."
        )

        return False

    if not is_admin(
        message.chat.id,
        message.from_user.id
    ):

        bot.reply_to(
            message,
            "❌ Only group administrators can use this command."
        )

        return False

    return True


def bot_admin_required(message):

    try:

        me = bot.get_me()

        member = bot.get_chat_member(
            message.chat.id,
            me.id
        )

        if member.status != "administrator":

            bot.reply_to(
                message,
                "❌ I need to be an administrator to do this."
            )

            return False

        return True

    except Exception:

        return False


def format_user(user):

    if user.username:

        return f"@{user.username}"

    first_name = user.first_name or "User"

    return (
        f"<a href='tg://user?id={user.id}'>"
        f"{first_name}"
        f"</a>"
    )


# ============================================================
# START
# ============================================================

@bot.message_handler(commands=["start"])
def start(message):

    text = (
        "🤖 <b>Group Management Bot</b>\n\n"

        "I can help administrators manage groups.\n\n"

        "📌 <b>Moderation</b>\n"
        "/ban\n"
        "/unban\n"
        "/kick\n"
        "/mute\n"
        "/unmute\n"
        "/warn\n"
        "/warnings\n"
        "/clearwarns\n\n"

        "👮 <b>Administration</b>\n"
        "/promote\n"
        "/demote\n"
        "/admins\n\n"

        "📌 <b>Messages</b>\n"
        "/pin\n"
        "/unpin\n\n"

        "ℹ️ <b>Information</b>\n"
        "/id\n"
        "/help\n\n"

        "💡 Reply to a user's message before using "
        "moderation commands."
    )

    bot.reply_to(
        message,
        text
    )


# ============================================================
# HELP
# ============================================================

@bot.message_handler(commands=["help"])
def help_command(message):

    text = (
        "🤖 <b>GROUP MANAGEMENT HELP</b>\n\n"

        "🔨 <b>Moderation</b>\n"
        "<code>/ban</code> - Ban user\n"
        "<code>/unban</code> - Unban user\n"
        "<code>/kick</code> - Remove user\n"
        "<code>/mute</code> - Mute user\n"
        "<code>/unmute</code> - Unmute user\n"
        "<code>/warn</code> - Give warning\n"
        "<code>/warnings</code> - Check warnings\n"
        "<code>/clearwarns</code> - Clear warnings\n\n"

        "👮 <b>Admin</b>\n"
        "<code>/promote</code> - Promote user\n"
        "<code>/demote</code> - Demote admin\n"
        "<code>/admins</code> - List admins\n\n"

        "📌 <b>Messages</b>\n"
        "<code>/pin</code> - Pin replied message\n"
        "<code>/unpin</code> - Unpin message\n\n"

        "ℹ️ <b>Info</b>\n"
        "<code>/id</code> - Show user/chat ID\n\n"

        "💡 <b>Tip:</b>\n"
        "Reply to a user's message and use the command."
    )

    bot.reply_to(
        message,
        text
    )


# ============================================================
# ID
# ============================================================

@bot.message_handler(commands=["id"])
def id_command(message):

    if message.reply_to_message:

        user = message.reply_to_message.from_user

        bot.reply_to(
            message,
            f"👤 <b>User ID:</b> "
            f"<code>{user.id}</code>\n"
            f"💬 <b>Chat ID:</b> "
            f"<code>{message.chat.id}</code>"
        )

    else:

        bot.reply_to(
            message,
            f"👤 <b>Your ID:</b> "
            f"<code>{message.from_user.id}</code>\n"
            f"💬 <b>Chat ID:</b> "
            f"<code>{message.chat.id}</code>"
        )


# ============================================================
# BAN
# ============================================================

@bot.message_handler(commands=["ban"])
def ban_command(message):

    if not admin_required(message):
        return

    if not bot_admin_required(message):
        return

    user = get_target_from_reply_or_command(message)

    if not user:
        return

    if is_admin(
        message.chat.id,
        user.id
    ):

        bot.reply_to(
            message,
            "❌ You cannot ban an administrator."
        )

        return

    try:

        bot.ban_chat_member(
            message.chat.id,
            user.id
        )

        bot.reply_to(
            message,
            f"🔨 <b>Banned</b>\n\n"
            f"👤 User: {format_user(user)}"
        )

    except Exception as e:

        bot.reply_to(
            message,
            "❌ Failed to ban user.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# UNBAN
# ============================================================

@bot.message_handler(commands=["unban"])
def unban_command(message):

    if not admin_required(message):
        return

    if not bot_admin_required(message):
        return

    user = get_target_from_reply_or_command(message)

    if not user:
        return

    try:

        bot.unban_chat_member(
            message.chat.id,
            user.id,
            only_if_banned=True
        )

        bot.reply_to(
            message,
            f"✅ <b>Unbanned</b>\n\n"
            f"👤 User: {format_user(user)}"
        )

    except Exception as e:

        bot.reply_to(
            message,
            f"❌ Failed.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# KICK
# ============================================================

@bot.message_handler(commands=["kick"])
def kick_command(message):

    if not admin_required(message):
        return

    if not bot_admin_required(message):
        return

    user = get_target_from_reply_or_command(message)

    if not user:
        return

    if is_admin(
        message.chat.id,
        user.id
    ):

        bot.reply_to(
            message,
            "❌ You cannot kick an administrator."
        )

        return

    try:

        bot.ban_chat_member(
            message.chat.id,
            user.id
        )

        bot.unban_chat_member(
            message.chat.id,
            user.id
        )

        bot.reply_to(
            message,
            f"👢 <b>Kicked</b>\n\n"
            f"👤 User: {format_user(user)}"
        )

    except Exception as e:

        bot.reply_to(
            message,
            f"❌ Failed.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# MUTE
# ============================================================

@bot.message_handler(commands=["mute"])
def mute_command(message):

    if not admin_required(message):
        return

    if not bot_admin_required(message):
        return

    user = get_target_from_reply_or_command(message)

    if not user:
        return

    if is_admin(
        message.chat.id,
        user.id
    ):

        bot.reply_to(
            message,
            "❌ You cannot mute an administrator."
        )

        return

    try:

        permissions = ChatPermissions(
            can_send_messages=False
        )

        until_date = (
            int(time.time())
            + DEFAULT_MUTE_SECONDS
        )

        bot.restrict_chat_member(
            message.chat.id,
            user.id,
            permissions=permissions,
            until_date=until_date
        )

        mute_tracker[
            (message.chat.id, user.id)
        ] = until_date

        bot.reply_to(
            message,
            f"🔇 <b>Muted</b>\n\n"
            f"👤 User: {format_user(user)}\n"
            f"⏱ Duration: 5 minutes"
        )

    except Exception as e:

        bot.reply_to(
            message,
            f"❌ Failed.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# UNMUTE
# ============================================================

@bot.message_handler(commands=["unmute"])
def unmute_command(message):

    if not admin_required(message):
        return

    if not bot_admin_required(message):
        return

    user = get_target_from_reply_or_command(message)

    if not user:
        return

    try:

        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )

        bot.restrict_chat_member(
            message.chat.id,
            user.id,
            permissions=permissions
        )

        mute_tracker.pop(
            (message.chat.id, user.id),
            None
        )

        bot.reply_to(
            message,
            f"🔊 <b>Unmuted</b>\n\n"
            f"👤 User: {format_user(user)}"
        )

    except Exception as e:

        bot.reply_to(
            message,
            f"❌ Failed.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# WARN
# ============================================================

@bot.message_handler(commands=["warn"])
def warn_command(message):

    if not admin_required(message):
        return

    user = get_target_from_reply_or_command(message)

    if not user:
        return

    if user.id == message.from_user.id:

        bot.reply_to(
            message,
            "❌ You cannot warn yourself."
        )

        return

    if is_admin(
        message.chat.id,
        user.id
    ):

        bot.reply_to(
            message,
            "❌ You cannot warn an administrator."
        )

        return

    chat_id = message.chat.id

    warnings_db[
        chat_id
    ][user.id] += 1

    count = warnings_db[
        chat_id
    ][user.id]

    if count >= MAX_WARNINGS:

        if bot_admin_required(message):

            try:

                bot.ban_chat_member(
                    chat_id,
                    user.id
                )

                warnings_db[
                    chat_id
                ][user.id] = 0

                bot.reply_to(
                    message,
                    f"🚫 <b>User banned</b>\n\n"
                    f"👤 {format_user(user)}\n"
                    f"⚠️ Reached "
                    f"{MAX_WARNINGS} warnings."
                )

            except Exception as e:

                bot.reply_to(
                    message,
                    f"⚠️ User reached "
                    f"{MAX_WARNINGS} warnings "
                    f"but could not be banned.\n\n"
                    f"<code>{e}</code>"
                )

        return

    bot.reply_to(
        message,
        f"⚠️ <b>Warning</b>\n\n"
        f"👤 User: {format_user(user)}\n"
        f"⚠️ Warnings: "
        f"{count}/{MAX_WARNINGS}"
    )


# ============================================================
# WARNINGS
# ============================================================

@bot.message_handler(commands=["warnings"])
def warnings_command(message):

    user = get_target_user(message)

    if not user:
        user = message.from_user

    count = warnings_db[
        message.chat.id
    ][user.id]

    bot.reply_to(
        message,
        f"⚠️ <b>Warnings</b>\n\n"
        f"👤 User: {format_user(user)}\n"
        f"⚠️ Warnings: "
        f"{count}/{MAX_WARNINGS}"
    )


# ============================================================
# CLEAR WARNINGS
# ============================================================

@bot.message_handler(commands=["clearwarns"])
def clearwarns_command(message):

    if not admin_required(message):
        return

    user = get_target_from_reply_or_command(message)

    if not user:
        return

    warnings_db[
        message.chat.id
    ][user.id] = 0

    bot.reply_to(
        message,
        f"✅ Warnings cleared for "
        f"{format_user(user)}."
    )


# ============================================================
# PROMOTE
# ============================================================

@bot.message_handler(commands=["promote"])
def promote_command(message):

    if not admin_required(message):
        return

    if not bot_admin_required(message):
        return

    user = get_target_from_reply_or_command(message)

    if not user:
        return

    if not is_owner(
        message.chat.id,
        message.from_user.id
    ):

        bot.reply_to(
            message,
            "❌ Only the group owner can "
            "promote users."
        )

        return

    try:

        bot.promote_chat_member(
            message.chat.id,
            user.id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=False,
            can_change_info=True,
            can_invite_users=True,
            can_pin_messages=True
        )

        bot.reply_to(
            message,
            f"👮 <b>Promoted</b>\n\n"
            f"👤 {format_user(user)}"
        )

    except Exception as e:

        bot.reply_to(
            message,
            f"❌ Failed.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# DEMOTE
# ============================================================

@bot.message_handler(commands=["demote"])
def demote_command(message):

    if not admin_required(message):
        return

    if not bot_admin_required(message):
        return

    if not is_owner(
        message.chat.id,
        message.from_user.id
    ):

        bot.reply_to(
            message,
            "❌ Only the group owner can "
            "demote admins."
        )

        return

    user = get_target_from_reply_or_command(message)

    if not user:
        return

    try:

        bot.promote_chat_member(
            message.chat.id,
            user.id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_manage_video_chats=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False
        )

        bot.reply_to(
            message,
            f"⬇️ <b>Demoted</b>\n\n"
            f"👤 {format_user(user)}"
        )

    except Exception as e:

        bot.reply_to(
            message,
            f"❌ Failed.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# ADMINS
# ============================================================

@bot.message_handler(commands=["admins"])
def admins_command(message):

    if not is_group(message):
        return

    try:

        admins = bot.get_chat_administrators(
            message.chat.id
        )

        text = "👮 <b>GROUP ADMINS</b>\n\n"

        for index, admin in enumerate(
            admins,
            start=1
        ):

            user = admin.user

            if admin.status == "creator":
                role = "👑 Owner"
            else:
                role = "🛡 Admin"

            text += (
                f"{index}. "
                f"{format_user(user)} "
                f"— {role}\n"
            )

        bot.reply_to(
            message,
            text
        )

    except Exception as e:

        bot.reply_to(
            message,
            f"❌ Failed.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# PIN
# ============================================================

@bot.message_handler(commands=["pin"])
def pin_command(message):

    if not admin_required(message):
        return

    if not bot_admin_required(message):
        return

    if not message.reply_to_message:

        bot.reply_to(
            message,
            "❌ Reply to the message "
            "you want to pin."
        )

        return

    try:

        bot.pin_chat_message(
            message.chat.id,
            message.reply_to_message.message_id,
            disable_notification=True
        )

        bot.reply_to(
            message,
            "📌 Message pinned."
        )

    except Exception as e:

        bot.reply_to(
            message,
            f"❌ Failed.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# UNPIN
# ============================================================

@bot.message_handler(commands=["unpin"])
def unpin_command(message):

    if not admin_required(message):
        return

    if not bot_admin_required(message):
        return

    try:

        bot.unpin_chat_message(
            message.chat.id
        )

        bot.reply_to(
            message,
            "📌 Message unpinned."
        )

    except Exception as e:

        bot.reply_to(
            message,
            f"❌ Failed.\n"
            f"<code>{e}</code>"
        )


# ============================================================
# ANTI-SPAM
# ============================================================

@bot.message_handler(
    func=lambda message:
        message.chat.type
        in ["group", "supergroup"]
)
def anti_spam(message):

    if not message.from_user:
        return

    # Ignore bots
    if message.from_user.is_bot:
        return

    # Ignore administrators
    if is_admin(
        message.chat.id,
        message.from_user.id
    ):
        return

    key = (
        message.chat.id,
        message.from_user.id
    )

    now = time.time()

    tracker = spam_tracker[key]

    tracker.append(now)

    while (
        tracker
        and now - tracker[0] > SPAM_WINDOW
    ):
        tracker.popleft()

    if len(tracker) >= SPAM_MESSAGE_LIMIT:

        if not bot_admin_required(message):
            return

        try:

            bot.delete_message(
                message.chat.id,
                message.message_id
            )

            permissions = ChatPermissions(
                can_send_messages=False
            )

            until_date = (
                int(time.time()) + 60
            )

            bot.restrict_chat_member(
                message.chat.id,
                message.from_user.id,
                permissions=permissions,
                until_date=until_date
            )

            tracker.clear()

            bot.send_message(
                message.chat.id,
                f"🚨 <b>Anti-Spam</b>\n\n"
                f"👤 "
                f"{format_user(message.from_user)} "
                f"has been muted for 1 minute."
            )

        except Exception:
            pass


# ============================================================
# MEMBER EVENTS
# ============================================================

@bot.message_handler(
    content_types=[
        "new_chat_members",
        "left_chat_member"
    ]
)
def member_events(message):
    pass


# ============================================================
# VERCEL HOME
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return (
        "🤖 Group Management Bot is running!"
    ), 200


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.route(
    "/api/webhook",
    methods=["POST"]
)
def webhook():

    try:

        json_string = (
            request
            .get_data()
            .decode("utf-8")
        )

        update = (
            telebot.types.Update
            .de_json(json_string)
        )

        bot.process_new_updates(
            [update]
        )

        return "OK", 200

    except Exception as e:

        print(
            f"Webhook error: {e}"
        )

        return "ERROR", 500
