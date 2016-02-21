import os
import json

from discord.ext import commands
import asyncio_redis

bot = commands.Bot(command_prefix="!", description="TIT Testing Bot")

if os.environ.get("EXTERNAL"):
    test = ""
    secrets = {
        "redis_host": os.environ.get("redis_host"),
        "redis_password": os.environ.get("redis_password", None),
        "redis_port": os.environ.get("redis_port", 6379),
        "redis_db": os.environ.get("redis_db", 0),
        "discord_user": os.environ.get("discord_user"),
        "discord_password": os.environ.get("discord_password")
    }
else:
    test = "$Test "
    with open("../Other-Secrets/TITDev_discord.json") as secrets_file:
        secrets = json.load(secrets_file)


# Triggers
@bot.command()
async def register(trigger, reply):
    redis_connection = await asyncio_redis.Connection.create(host=secrets["redis_host"],
                                                             port=int(secrets["redis_port"]),
                                                             db=int(secrets["redis_db"]),
                                                             password=secrets["redis_password"])
    await redis_connection.hset("triggers", trigger, reply)
    redis_connection.close()
    await bot.say("{0}Trigger: {1}, Reply: {2}".format(test, trigger, reply))


@bot.command()
async def unregister(*triggers):
    redis_connection = await asyncio_redis.Connection.create(host=secrets["redis_host"],
                                                             port=int(secrets["redis_port"]),
                                                             db=int(secrets["redis_db"]),
                                                             password=secrets["redis_password"])
    await redis_connection.hdel("triggers", list(triggers))
    redis_connection.close()
    await bot.say("{0}Removed Trigger(s): {1}".format(test, ", ".join(triggers)))


@bot.command()
async def get(store):
    redis_connection = await asyncio_redis.Connection.create(host=secrets["redis_host"],
                                                             port=int(secrets["redis_port"]),
                                                             db=int(secrets["redis_db"]),
                                                             password=secrets["redis_password"])
    response = await redis_connection.hgetall(store)
    store_values = await response.asdict()
    message = "\n".join(["{0}: {1}".format(key, value) for key, value in store_values.items()])
    if not message.strip():
        message = "None"
    redis_connection.close()
    await bot.say("{0}```\n".format(test) + message + "\n```")


@bot.command()
async def name(*new_name):
    await bot.edit_profile(secrets["discord_password"], username=" ".join(new_name))


@bot.listen('on_message')
async def custom_message(message):
    if message.author.id != bot.user.id and not message.content.startswith("!"):
        redis_connection = await asyncio_redis.Connection.create(host=secrets["redis_host"],
                                                                 port=int(secrets["redis_port"]),
                                                                 db=int(secrets["redis_db"]),
                                                                 password=secrets["redis_password"])
        response = await redis_connection.hgetall("triggers")
        trigger_dict = await response.asdict()
        text = message.content.lower()
        for trigger, reply in trigger_dict.items():
            if text.find(trigger.lower()) != -1:
                # noinspection PyUnresolvedReferences
                await bot.send_message(message.channel, test + reply)


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
    test_channel = None
    for channel in bot.get_all_channels():
        if channel.name == "service_marketeer":
            marketeer_channel = channel
        elif channel.name == "hook_test":
            test_channel = channel

    while True:
        message = await subscriber.next_published()
        if message.channel == "titdev-marketeer":
            # Message to everyone
            formatted_message = "{0}".format(
                message.value
            )
            # noinspection PyUnresolvedReferences
            await bot.send_message(marketeer_channel, formatted_message)
        else:
            print(message.value)
            # noinspection PyUnresolvedReferences
            await bot.send_message(test_channel, message)

    redis_connection.close()


if __name__ == "__main__":
    bot.run(secrets["discord_user"], secrets["discord_password"])
