import discord
import re
from discord.ext.commands import Cog, MemberConverter, CommandError
from discord.ext import commands

from src.list_embed import ListEmbed

STAR = "⭐"
TRASH = u"\U0001F5D1"
OPEN_FOLDER = u"\U0001F4C2"
BOT_FACE = u"\U0001F916"
SHIELD = u"\U0001F6E1"
LOCK_KEY = u"\U0001F510"
SWORDS = u"\U00002694"
HAMMER_PICK = u"\U00002692"
HAMMER = u"\U0001F528"
CHAIN = u"\U000026D3"
HEADPHONES = u"\U0001F3A7"
EXCLAMATION = u"\U00002757"


class SettingsElement:
    '''Template for a setting element'''

    TRUE_STRINGS = ('1', 'true', 'yes', 'y')
    FALSE_STRINGS = ('0', 'false', 'no', 'n')

    def __init__(
            self,
            title: str,
            emoji: str,
            description: str,
            setting: str,
            success_msg: str = "Setting Updated",
            failure_msg: str = "Setting Unchanged"):
        self._title = title
        self.emoji = emoji
        self._description = description
        self.setting = setting
        self.success_msg = success_msg
        self.failure_msg = failure_msg

    @property
    def title(self):
        return f"{self.emoji} {self._title}"

    @property
    def description(self):
        return f"{self.emoji} {self._description}"

    def check(self, msg):
        '''if any check needs to be made for the edit message'''
        return True

    async def formatted_value(self, bot, ctx, settings):
        '''the value displayed in the embed'''
        return getattr(settings, self.setting)

    async def parse(self, msg, settings):
        '''parses a message for new values and returns them or raises ValueError'''
        if msg.clean_content.lower() in SettingsElement.TRUE_STRINGS:
            return True
        elif msg.clean_content.lower() in SettingsElement.FALSE_STRINGS:
            return False
        raise ValueError


class StarboardThreshold(SettingsElement):
    def __init__(self):
        super().__init__(
            "Starboard Threshold",
            STAR,
            "This is the number of reacts a message must get to be starboarded. Enter a number to modify it:",
            'starboard_threshold')

    async def parse(self, msg, settings):
        return abs(int(msg.clean_content))


class UserCommandThreshold(SettingsElement):
    def __init__(self):
        super().__init__(
            "Responses Limit",
            CHAIN,
            "This is the number of custom responses each user can set. Enter a number to modify it:",
            'responses_limit')

    async def parse(self, msg, settings):
        return abs(int(msg.clean_content))


class RepostDeletes(SettingsElement):
    def __init__(self):
        super().__init__(
            "Repost Deleted Messages",
            TRASH,
            "If true, deleted messages will be reposted immediately. Enter `true` or `false` to modify it:",
            'repost_del_msg')


class ManageEmojis(SettingsElement):
    def __init__(self):
        super().__init__(
            "Emoji Manager",
            OPEN_FOLDER,
            "If true, less popular emojis will be cycled in and out as needed, effectively "
            "allowing greater than 50 emojis. Enter `true` or `false` to modify it:",
            'manage_emojis')


class BotCommands(SettingsElement):
    def __init__(self):
        super().__init__(
            "Bot Commands Channels",
            BOT_FACE,
            "Some verbose commands are limited to these channels. Mention channels to toggle them:",
            'bot_commands_channels')

    async def formatted_value(self, bot, ctx, settings):
        return ', '.join([c.mention for c in [discord.utils.get(ctx.guild.channels, id=i)
                          for i in settings.bot_commands_channels] if c] or ['None'])

    async def parse(self, msg, settings):
        bc_channels = settings.bot_commands_channels

        for channel in msg.channel_mentions:
            if channel.id in bc_channels:
                bc_channels.remove(channel.id)
            else:
                bc_channels.append(channel.id)
        else:
            raise ValueError
        return bc_channels


class Admins(SettingsElement):
    def __init__(self):
        super().__init__(
            "Architus Admins",
            LOCK_KEY,
            "These members have access to more bot functions such as `purge` "
            "and setting longer commands. Mention a member to toggle:",
            'admin_ids')

    async def formatted_value(self, bot, ctx, settings):
        return ', '.join({(await bot.fetch_user(u)).name for u in settings.admins_ids})

    async def parse(self, msg, settings):
        member_converter = MemberConverter()
        try:
            member = await member_converter.convert(msg, msg.clean_content)
        except CommandError as e:
            # TODO does this work
            print(e)
            raise ValueError
        if member.id in settings.admin_ids:
            return settings.admin_ids.remove(member.id)
        else:
            return settings.admins_ids.append(member.id)


class DefaultRole(SettingsElement):
    def __init__(self):
        super().__init__(
            "Default Role",
            SHIELD,
            "New members will be automatically moved into this role. Enter a role id (`!roleids`) to change:",
            'default_role_id')

    async def formatted_value(self, bot, ctx, settings):
        default_role = discord.utils.get(ctx.guild.roles, id=settings.default_role_id)
        return default_role.mention if default_role else "None"

    def check(self, msg):
        return not msg.content.endswith('roleids')

    async def parse(self, msg, settings):
        if discord.utils.get(msg.guild.roles, id=int(msg.content)):
            return msg.content
        raise ValueError


class JoinableRoles(SettingsElement):
    def __init__(self):
        super().__init__(
            "Joinable Roles",
            SWORDS,
            "These are the roles that any member can join at will. Enter a list of role ids "
            "(`!roleids`) to toggle. Optionally enter a nickname for the role in the format "
            "`nickname::roleid` if the role's name is untypable:",
            'roles_dict')

    async def formatted_value(self, bot, ctx, settings):
        return ', '.join([r.mention for r in [discord.utils.get(ctx.guild.roles, id=i)
                         for i in settings.roles_dict.values()] if r] or ['None'])

    def check(self, msg):
        return not msg.content.endswith('roleids')

    async def parse(self, msg, settings):
        pattern = re.compile(r"((?P<nick>\w+)::)?(?P<id>\d{17,20})")
        new_roles = []
        roles = settings.roles_dict
        for match in re.finditer(pattern, msg.content):
            role = discord.utils.get(msg.guild.roles, id=int(match.group('id')))
            if match.group('nick') and role:
                new_roles.append((match.group('nick').lower(), role.id))
            elif role:
                new_roles.append((role.name.lower(), role.id))
        for role in new_roles:
            if role[1] in roles.values():  # if role already in dict
                if role[0] not in roles:  # in dict with a different nick
                    roles = {k: v for k, v in roles.items() if v != role[1]}
                    roles[role[0]] = role[1]
                else:                     # in dict with the same nick
                    roles = {k: v for k, v in roles.items() if v != role[1]}
            else:                         # new role
                roles[role[0]] = role[1]
        else:
            raise ValueError

        return roles


class GulagThreshold(SettingsElement):
    def __init__(self):
        super().__init__(
            "Gulag Threshold",
            HAMMER_PICK,
            'This is the number of reacts a gulag vote must get to be pass. Enter a number to modify it:',
            'gulag_threshold')

    async def parse(self, msg, settings):
        return abs(int(msg.clean_content))


class GulagSeverity(SettingsElement):
    def __init__(self):
        super().__init__(
            "Gulag Severity",
            HAMMER,
            'This is the number of minutes a member will be confined to gulag. '
            'Half again per extra vote. Enter a number to modify it:',
            'gulag_severity')

    async def parse(self, msg, settings):
        return abs(int(msg.clean_content))


class MusicEnabled(SettingsElement):
    def __init__(self):
        super().__init__(
            "Music Enabled",
            HEADPHONES,
            "Whether music related features are enabled. Enter `true` or `false` to set.",
            'music_enabled')


class CommandPrefix(SettingsElement):
    def __init__(self):
        super().__init__(
            "Command Prefix",
            EXCLAMATION,
            "The prefix before a message to indicate"
            " that it is a command for Architus. Enter a new prefix or `cancel` to leave unchanged.",
            'command_prefix')

    async def formatted_value(self, bot, ctx, settings):
        return f"'{getattr(settings, self.setting)}'"

    async def parse(self, msg, settings):
        if msg.clean_content == 'cancel':
            raise ValueError
        return msg.clean_content


class Settings(Cog):
    '''
    Manage server specific architus settings
    '''

    def __init__(self, bot):
        self.bot = bot
        self.settings_elements = [cls() for cls in SettingsElement.__subclasses__()]

    @commands.command(hidden=True)
    async def roleids(self, ctx):
        '''Shows the discord id for every role in your server'''
        lem = ListEmbed(ctx.guild.name, '')
        lem.name = "Role IDs"
        for role in ctx.guild.roles:
            lem.add(role.name, role.id)
        await ctx.channel.send(embed=lem.get_embed())

    @commands.command()
    async def settings(self, ctx):
        '''Open an interactive settings dialog'''
        settings = self.bot.settings[ctx.guild]
        if ctx.author.id not in settings.admins_ids:
            await ctx.channel.send('nope, sorry')
            return

        msg = await ctx.channel.send(embed=await self.get_embed(ctx, settings))

        for setting in self.settings_elements:
            await msg.add_reaction(setting.emoji)

        # TODO not forever
        while True:
            react, user = await self.bot.wait_for(
                'reaction_add', check=lambda r, u: r.message.id == msg.id and u == ctx.author)
            for setting in self.settings_elements:
                if react.emoji == setting.emoji:
                    await ctx.send(setting.description)
                    user_msg = await self.bot.wait_for(
                        'message', check=lambda m: m.author == ctx.author and setting.check(msg))
                    try:
                        value = await setting.parse(user_msg, settings)
                    except ValueError:
                        await ctx.send(setting.failure_msg)
                    else:
                        setattr(settings, setting.setting, value)
                        await ctx.send(setting.success_msg)
            await msg.edit(embed=await self.get_embed(ctx, settings))

    async def get_embed(self, ctx, settings):
        em = discord.Embed(
            title="⚙ Settings",
            description="Select an item for more info or to change it",
            colour=0x83bdff,
            url=f'https://archit.us/app/{ctx.guild.id}/settings')
        em.set_author(name='Architus Server Settings', icon_url=str(ctx.guild.icon_url))

        for setting in self.settings_elements:
            value = await setting.formatted_value(self.bot, ctx, settings)
            em.add_field(name=setting.title, value=f"Value: {value}", inline=True)
        return em


def setup(bot):
    bot.add_cog(Settings(bot))
