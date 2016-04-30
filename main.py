import os
import json
import re
import asyncio

from discord.ext import commands
# noinspection PyPackageRequirements
import asyncio_redis

if os.environ.get("EXTERNAL"):
    command_prefix = "!"
    secrets = {
        "redis_host": os.environ.get("redis_host"),
        "redis_password": os.environ.get("redis_password", None),
        "redis_port": os.environ.get("redis_port", 6379),
        "redis_db": os.environ.get("redis_db", 0),
        "discord_user": os.environ.get("discord_user"),
        "discord_password": os.environ.get("discord_password"),
        "discord_bot_username": os.environ.get("discord_bot_username"),
        "discord_bot_id": os.environ.get("discord_bot_id"),
        "discord_bot_token": os.environ.get("discord_bot_token")
    }
else:
    command_prefix = "$"
    with open("../Other-Secrets/TITDev_discord.json") as secrets_file:
        secrets = json.load(secrets_file)

# Other Settings
with open("config.json") as config_file:
    config = json.load(config_file)

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
        # Remove mentions
        user_ids = re.findall("<@(.*?)>", message)
        user_map = {}
        for member in bot.get_all_members():
            if member.id in user_ids:
                user_map[member.id] = member.name
        for key, value in user_map.items():
            message = message.replace("<@{0}>".format(key), "<{0}>".format(value))
        message = re.sub("<@.*?>", "", message)

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
    await bot.say("I shall now be known as <{0}>. Fear me!".format(" ".join(new_name)))


@bot.command(description="Lists all server roles", brief=":: (none) :: Lists all server roles [All Users]",
             pass_context=True)
async def roles(ctx):
    await bot.say("```Roles: {0}```".format([x.name for x in ctx.message.server.roles if not x.name.startswith("@")]))


@bot.command(description="Displays server id", brief=":: (none) :: Displays server id [All Users]",
             pass_context=True)
async def server_id(ctx):
    await bot.say("ID: {0}".format(ctx.message.server.id))


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
    await subscriber.subscribe(["titdev-marketeer", "titdev-recruitment", "titdev-auth",
                                "titdev-test"])

    marketeer_channel = None
    test_channel = None
    recruitment_channel = None
    main_server = None

    for server in bot.servers:
        if server.name == config["main_server_name"]:
            main_server = server
    for channel in bot.get_all_channels():
        if channel.server == main_server:
            if channel.name == config["marketeer_channel_name"]:
                marketeer_channel = channel
            elif channel.name == config["recruitment_channel_name"]:
                recruitment_channel = channel
            elif channel.name == config["test_channel_name"]:
                test_channel = channel

    while True:
        print("Ready @ {0}".format(main_server.name))
        message = await subscriber.next_published()
        print("{1} @ {0}".format(main_server.name, message.channel))
        if message.channel == "titdev-marketeer":
            formatted_message = "{0}".format(
                message.value
            )
            # noinspection PyUnresolvedReferences
            await bot.send_message(marketeer_channel, formatted_message)
        elif message.channel == "titdev-recruitment":
            formatted_message = "{0}".format(
                message.value
            )
            # noinspection PyUnresolvedReferences
            await bot.send_message(recruitment_channel, formatted_message)
        elif message.channel == "titdev-auth":
            print(message.value)
            await asyncio.sleep(config["rate_wait"])
            standings = [config["role_prefix"] + x for x in ["Corporation", "Alliance", "+10", "+5"]]
            custom = [config["role_prefix"] + "nsfw"]
            if message.value.startswith("!"):
                auto_role_list = [config["role_prefix"] + x for x in message.value[1:].split()]
                delete_role_list = []
                # Delete roles removed from role list
                for role in main_server.roles:
                    if role.name in auto_role_list:
                        auto_role_list.remove(role.name)
                    elif role.name.startswith(config["role_prefix"]) and role.name not in standings + custom:
                        delete_role_list.append(role)
                for role in delete_role_list:
                    await bot.delete_role(main_server, role)
                # Add new roles
                if auto_role_list:
                    for new_role in auto_role_list:
                        # noinspection PyUnresolvedReferences
                        await bot.create_role(main_server, name=new_role)
            elif message.value.startswith("&"):
                # Role toggling

                member_id = message.value.split()[0][1:]
                auto_role = config["role_prefix"] + message.value.split()[1]
                enable_role = True if message.value.split()[2] == "True" else False
                # Add role if doesn't exist
                new_role = True
                for role in main_server.roles:
                    if role.name == auto_role:
                        new_role = False
                if new_role:
                    # noinspection PyUnresolvedReferences
                    await bot.create_role(main_server, name=auto_role)
                # Find member
                member_auth = None
                for member in main_server.members:
                    if member_id.strip() == member.id:
                        member_auth = member
                if member_auth:
                    # Find Role
                    new_role = None
                    for role in main_server.roles:
                        if role.name == auto_role:
                            new_role = role
                    if new_role:
                        if not enable_role:
                            await bot.remove_roles(member_auth, new_role)
                        else:
                            await bot.add_roles(member_auth, new_role)
                else:
                    print(member_id)
            elif message.value.startswith("@"):
                member_id = message.value.split()[0][1:]
                member_name = " ".join(message.value.split()[1:])[1:-1]
                member_auth = None

                # Find actual member
                for member in main_server.members:
                    if member_id.strip() == member.id:
                        member_auth = member

                if member_auth:
                    await bot.change_nickname(member_auth, member_name)
            else:
                member_id = message.value.split()[0]

                # Find actual member
                member_auth = None
                adjust_standing = False
                if member_id.startswith("#"):
                    member_id = member_id[1:]
                    adjust_standing = True
                for member in main_server.members:
                    if member_id.strip() == member.id:
                        member_auth = member
                if not member_auth:
                    print("Member ID {0} is not on this server".format(member_id))
                    continue

                if adjust_standing:
                    new_standing = message.value.split()[1]
                    server_standings = []
                    standing_role = None
                    for role in main_server.roles:
                        if role.name in standings:
                            server_standings.append(role)
                        if role.name.endswith("Corporation") and new_standing == "corporation":
                            standing_role = role
                        elif role.name.endswith("Alliance") and new_standing == "alliance":
                            standing_role = role
                        elif role.name.endswith("+10") and new_standing == "+10":
                            standing_role = role
                        elif role.name.endswith("+5") and new_standing == "+5":
                            standing_role = role
                    if server_standings:
                        await bot.remove_roles(member_auth, *server_standings)
                    if standing_role:
                        await bot.add_roles(member_auth, standing_role)
                    else:
                        print("{0} standing revoked to: {1}".format(member_auth.name, new_standing))
                else:
                    member_roles = [config["role_prefix"] + x for x in message.value.split()[1:]]
                    # Remove all auto-roles
                    old_role_list = []
                    for old_role in member_auth.roles:
                        if old_role.name.startswith(config["role_prefix"]) and old_role.name not in standings + custom:
                            old_role_list.append(old_role)
                    if old_role_list:
                        await bot.remove_roles(member_auth, *old_role_list)
                    # Add auto-roles
                    new_role_list = []
                    for role in main_server.roles:
                        if role.name in member_roles:
                            new_role_list.append(role)
                    if new_role_list:
                        await bot.add_roles(member_auth, *new_role_list)
        else:
            print(message.value)
            # noinspection PyUnresolvedReferences
            await bot.send_message(test_channel, message)

    redis_connection.close()


if __name__ == "__main__":
    bot.run(secrets["discord_bot_token"])
