import os
import json

from discord.ext import commands
import asyncio_redis

bot = commands.Bot(command_prefix="!", description="TIT Testing Bot")

if os.environ.get("EXTERNAL"):
    secrets = {
        "redis_host": os.environ.get("redis_host"),
        "redis_password": os.environ.get("redis_password", None),
        "redis_port": os.environ.get("redis_port", 6379),
        "redis_db": os.environ.get("redis_db", 0)
    }
else:
    with open("../Other-Secrets/TITDev_discord.json") as secrets_file:
        secrets = json.load(secrets_file)


@bot.command()
async def activate_slackbot():
    await bot.say("I have returned!")


@bot.command()
async def register(group, member):
    await bot.say("{1} has registered been to {0}".format(group, member))


@bot.listen('on_message')
async def custom_message(message):
    to_user = None
    for user in bot.get_all_members():
        if user.name == "Stroker":
            to_user = user
    if message.content.find("handjobs") != -1 and to_user:
        # noinspection PyUnresolvedReferences
        await bot.send_message(message.channel, "{0}, care to lend a hand?".format(to_user.mention))


@bot.event
async def on_ready():
    print("Logged in as: {0}, id={1}".format(bot.user.name, bot.user.id))
    # Redis
    redis_connection = await asyncio_redis.Pool.create(poolsize=10,
                                                       host=secrets["redis_host"],
                                                       port=int(secrets["redis_port"]),
                                                       db=int(secrets["redis_db"]),
                                                       password=secrets["redis_password"])
    subscriber = await redis_connection.start_subscribe()
    await subscriber.subscribe(["titdev-marketeer", "titdev-test"])

    marketeer_channel = None
    for channel in bot.get_all_channels():
        if channel.name == "service_marketeer":
            marketeer_channel = channel

    while True:
        message = await subscriber.next_published()
        if message.channel == "titdev-marketeer":
            # noinspection PyUnresolvedReferences
            await bot.send_message(marketeer_channel, message.value)
        else:
            print(message.value)

    redis_connection.close()


if __name__ == "__main__":
    bot.run(secrets["discord_user"], secrets["discord_password"])
