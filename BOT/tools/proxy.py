from pyrogram import Client, filters
from pyrogram.types import Message
import json, re, os, asyncio, httpx

PROXY_FILE = "DATA/proxy.json"

def load_proxies():
    return json.load(open(PROXY_FILE)) if os.path.exists(PROXY_FILE) else {}

def save_proxies(data):
    with open(PROXY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def normalize_proxy(proxy_raw: str) -> str:
    proxy_raw = proxy_raw.strip()

    # 1. Already full proxy URL
    if proxy_raw.startswith("http://") or proxy_raw.startswith("https://"):
        return proxy_raw

    # 2. Format: USER:PASS@HOST:PORT
    match1 = re.fullmatch(r"(.+?):(.+?)@([a-zA-Z0-9\.\-]+):(\d+)", proxy_raw)
    if match1:
        user, pwd, host, port = match1.groups()
        return f"http://{user}:{pwd}@{host}:{port}"

    # 3. Format: HOST:PORT:USER:PASS
    match2 = re.fullmatch(r"([a-zA-Z0-9\.\-]+):(\d+):(.+?):(.+)", proxy_raw)
    if match2:
        host, port, user, pwd = match2.groups()
        return f"http://{user}:{pwd}@{host}:{port}"

    return None

async def get_ip(proxy_url):
    try:
        transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
        async with httpx.AsyncClient(transport=transport, timeout=10) as client:
            res = await client.get("https://ipinfo.io/json")
            if res.status_code == 200:
                return res.json().get("ip"), None
            return None, res.status_code
    except Exception as e:
        return None, str(e)

def get_proxy(user_id: int) -> str | None:
    if not os.path.exists(PROXY_FILE):
        return None
    try:
        data = json.load(open(PROXY_FILE))
        return data.get(str(user_id))
    except Exception:
        return None

@Client.on_message(filters.command("setpx") & filters.private)
async def set_proxy(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("<b>Format ❌:</b> `/setpx {proxy}`", quote=True)

    raw_proxy = message.text.split(maxsplit=1)[1].strip()
    proxy_url = normalize_proxy(raw_proxy)

    if not proxy_url:
        return await message.reply(
            "<pre>Invalid format ❌</pre>\n<b>Supported:</b>\n~ {ip}:{port}:{user}:{pass}\n~ {user}:{pass}@{ip}:{port}\n~ {protocol}://{user}:{pass}@{ip}:{port}",
            quote=True,
        )

    user_id = str(message.from_user.id)
    data = load_proxies()

    if data.get(user_id) == proxy_url:
        return await message.reply("<b>This proxy is already added ⚠️</b>", quote=True)

    msg = await message.reply("<pre>Validating Proxy 🔘</pre>", quote=True)

    ip1, err1 = await get_ip(proxy_url)
    await asyncio.sleep(2)
    ip2, err2 = await get_ip(proxy_url)

    if not ip1 or not ip2:
        err_msg = err1 or err2 or "Unknown error"
        return await msg.edit(f"<pre>Connection Failure ❌</pre>\n<b>~ Error :</b> <code>{err_msg}</code>")

    if ip1 == ip2:
        return await msg.edit(f"<pre>Proxy Risk ⚠️</pre>\n<b>Message :</b> <code>Provided Proxy Seems To be Risky</code>\n<b>Try Rotating|Residential Proxy</b>")

    # Save or Replace proxy for user
    data[user_id] = proxy_url
    save_proxies(data)

    await msg.edit(f"<pre>Proxy saved successfully! ✅</pre>")

@Client.on_message(filters.command("delpx") & filters.private)
async def delete_proxy(client, message: Message):
    user_id = str(message.from_user.id)
    data = load_proxies()

    if user_id not in data:
        return await message.reply("<b>No proxy was found to delete !!!</b>", quote=True)

    del data[user_id]
    save_proxies(data)
    await message.reply("<b>Your proxy has been removed ✅</b>", quote=True)

@Client.on_message(filters.command("getpx") & filters.private)
async def getpx_handler(client, message):
    user_id = message.from_user.id
    proxy = get_proxy(user_id)

    if not proxy:
        return await message.reply("<b>You haven't set any proxy yet ❌</b>")

    try:
        # Remove http:// if present
        proxy = proxy.replace("http://", "")
        creds, hostport = proxy.split("@")
        username = creds.split(":")[0]
        host = hostport.split(":")[0]

        await message.reply(
            f"<pre>Proxy | {user_id}\n"
            f"✦ <b>Username:</b> <code>{username}</code>\n"
            f"✦ <b>Host:</b> <code>{host}</code>"
        )
    except Exception as e:
        await message.reply(f"❌ Failed to parse proxy.\n<code>{e}</code>")
