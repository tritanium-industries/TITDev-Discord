import os
import json

from discord.ext import commands
import asyncio_redis

if os.environ.get("EXTERNAL"):
    command_prefix = "!"
    secrets = {
        "redis_host": os.environ.get("redis_host"),
        "redis_password": os.environ.get("redis_password", None),
        "redis_port": os.environ.get("redis_port", 6379),
        "redis_db": os.environ.get("redis_db", 0),
        "discord_user": os.environ.get("discord_user"),
        "discord_password": os.environ.get("discord_password")
    }
else:
    command_prefix = "$"
    with open("../Other-Secrets/TITDev_discord.json") as secrets_file:
        secrets = json.load(secrets_file)

bot = commands.Bot(command_prefix=command_prefix, description="TIT Testing Bot")


# # Commands

# Triggers
@bot.group(description="Trigger related commands",
           brief='<Category> Lists triggers [All Users].',
           pass_context=True)
async def triggers(ctx):
    if ctx.invoked_subcommand is None:
        redis_connection = await asyncio_redis.Connection.create(host=secrets["redis_host"],
                                                                 port=int(secrets["redis_port"]),
                                                                 db=int(secrets["redis_db"]),
                                                                 password=secrets["redis_password"])
        response = await redis_connection.hgetall("triggers")
        store_values = await response.asdict()
        message = "\n".join(["{0}: {1}".format(key, value) for key, value in store_values.items()])
        if not message.strip():
            message = "None"
        redis_connection.close()
        await bot.say("```\n" + message + "\n```")


@triggers.command(description="Registers a trigger", brief=':: "trigger" "reply" :: Registers a trigger [Admin Only]',
                  pass_context=True)
async def register(ctx, new_trigger, reply):
    if {"Admin", "Developer"} & {x.name for x in ctx.message.author.roles}:
        redis_connection = await asyncio_redis.Connection.create(host=secrets["redis_host"],
                                                                 port=int(secrets["redis_port"]),
                                                                 db=int(secrets["redis_db"]),
                                                                 password=secrets["redis_password"])
        await redis_connection.hset("triggers", new_trigger, reply)
        redis_connection.close()
        await bot.say("Trigger: {0}, Reply: {1}".format(new_trigger, reply))
    else:
        await bot.say("You are not authorized to use this command.")


@triggers.command(description="Unregisters a trigger", brief=':: "trigger" :: Unregisters a trigger [Admin Only]',
                  pass_context=True)
async def unregister(ctx, *chosen_triggers):
    if {"Admin", "Developer"} & {x.name for x in ctx.message.author.roles}:
        redis_connection = await asyncio_redis.Connection.create(host=secrets["redis_host"],
                                                                 port=int(secrets["redis_port"]),
                                                                 db=int(secrets["redis_db"]),
                                                                 password=secrets["redis_password"])
        await redis_connection.hdel("triggers", list(chosen_triggers))
        redis_connection.close()
        await bot.say("Removed Trigger(s): {0}".format(", ".join(chosen_triggers)))
    else:
        await bot.say("You are not authorized to use this command.")


@bot.command(description="Change the name of the bot", brief=":: name :: Change the name of the bot [All Users]")
async def name(*new_name):
    await bot.edit_profile(secrets["discord_password"], username=" ".join(new_name))
    await bot.say("I shall now be known as <{0}>. Fear me!".format(new_name))


@bot.command(description="Lists your current roles", brief=":: (none) :: Lists your current roles [All Users]",
             pass_context=True)
async def roles(ctx):
    await bot.say("Roles: {0}".format(", ".join([x.name for x in ctx.message.author.roles
                                                 if not x.name.startswith("@")])))


# # Events

@bot.listen('on_message')
async def custom_message(message):
    if message.author.id != bot.user.id and not message.content.startswith("!") and command_prefix != "$":
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
                await bot.send_message(message.channel, reply)


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
