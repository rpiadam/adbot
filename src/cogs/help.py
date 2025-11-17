from __future__ import annotations

import itertools
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import discord
from discord import app_commands
from discord.ext import commands


class HelpCog(commands.Cog):
    """Context-aware help command grouping key functionality."""

    ADMIN_HELP_PATH = Path("docs/help/admin.md")
    SLASH_HELP_PATH = Path("docs/help/overview.md")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._slash_group = _HelpSlashGroup(self)
        self.bot.tree.add_command(self._slash_group)

    def cog_unload(self) -> None:
        self.bot.tree.remove_command(self._slash_group.name, type(self._slash_group))

    def _match_cog(self, name: str) -> commands.Cog | None:
        target = name.lower()
        for cog in self.bot.cogs.values():
            qualified = cog.qualified_name.lower()
            simple = qualified.removesuffix("cog")
            if target in {qualified, simple}:
                return cog
        return None

    def _iter_commands(self) -> Iterable[commands.Command]:
        seen = set()
        for command in self.bot.commands:
            if command.hidden or command.name in seen:
                continue
            seen.add(command.name)
            yield command

    def _build_overview_embed(self) -> discord.Embed:
        embed = discord.Embed(title="UpLove Help", colour=discord.Colour.green())
        embed.description = (
            "Key commands grouped by category. Use `/help category <name>` or `!help <category>` to drill down.\n"
            "Categories: Features, Games, Moderation, Admin, Music, Monitoring, RSS, POTA, Welcome."
        )

        grouped: Dict[str, List[str]] = {}

        def _add_entry(category: str, label: str) -> None:
            grouped.setdefault(category, []).append(label)

        for command in self._iter_commands():
            category_name = command.cog_name or "General"
            if category_name.endswith("Cog"):
                category_name = category_name[:-3]
            _add_entry(category_name, f"!{command.name}")

        for slash_command in self.bot.tree.walk_commands():
            binding = getattr(slash_command, "binding", None)
            category_name = getattr(binding, "qualified_name", "General")
            if category_name.endswith("Cog"):
                category_name = category_name[:-3]
            if slash_command.parent is not None:
                label = f"/{slash_command.parent.qualified_name} {slash_command.name}"
            else:
                label = f"/{slash_command.name}"
            _add_entry(category_name, label)

        for category_name, items in sorted(grouped.items()):
            display = ", ".join(itertools.islice(items, 5))
            remainder = len(items) - 5
            if remainder > 0:
                display += f" … (+{remainder} more)"
            embed.add_field(name=category_name, value=display or "No commands", inline=False)
        return embed

    def _load_markdown(self, path: Path) -> Optional[str]:
        if not path.exists():
            return None
        try:
            return path.read_text()
        except OSError:
            return None

    @commands.command(name="help")
    async def help(self, ctx: commands.Context, category: Optional[str] = None) -> None:
        """Display top-level help or describe a specific command category."""
        if category:
            cog = self._match_cog(category)
            if not cog:
                await ctx.send("Unknown category. Try `!help` for a full list.")
                return
            commands_list = cog.get_commands()
            if not commands_list:
                await ctx.send("No public commands in that category.")
                return
            embed = discord.Embed(
                title=f"{category.title()} Commands",
                colour=discord.Colour.blurple(),
            )
            for command in commands_list:
                name = getattr(command, "name", command.qualified_name)
                prefix = "/" if isinstance(command, app_commands.Command) else "!"
                description = getattr(command, "description", None) or command.help or "No description."
                embed.add_field(name=f"{prefix}{name}", value=description, inline=False)
            await ctx.send(embed=embed)
            return

        embed = self._build_overview_embed()
        await ctx.send(embed=embed)

    async def _slash_help_overview(self, interaction: discord.Interaction) -> None:
        embed = self._build_overview_embed()
        content = self._load_markdown(self.SLASH_HELP_PATH)
        if content:
            await interaction.response.send_message(content=content, embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _slash_help_category(self, interaction: discord.Interaction, name: str) -> None:
        cog = self._match_cog(name)
        if not cog:
            await interaction.response.send_message("Unknown category. Try `/help overview`.", ephemeral=True)
            return
        slash_commands = list(getattr(cog, "get_app_commands", lambda: [])())
        prefixed_commands = list(cog.get_commands())
        if not slash_commands and not prefixed_commands:
            await interaction.response.send_message("No public commands in that category.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{cog.qualified_name} Commands",
            colour=discord.Colour.blurple(),
        )
        for command in slash_commands:
            if command.parent:
                qualified = f"{command.parent.qualified_name} {command.name}"
            else:
                qualified = command.name
            description = command.description or "No description."
            embed.add_field(name=f"/{qualified}", value=description, inline=False)
        for command in prefixed_commands:
            description = getattr(command, "help", None) or "No description."
            embed.add_field(name=f"!{command.name}", value=description, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _slash_help_admin(self, interaction: discord.Interaction) -> None:
        content = self._load_markdown(self.ADMIN_HELP_PATH)
        if not content:
            await interaction.response.send_message(
                "Admin help documentation is not available.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(content, ephemeral=True)


class _HelpSlashGroup(app_commands.Group):
    def __init__(self, cog: HelpCog):
        super().__init__(name="help", description="Access documentation about the relay bot.")
        self._cog = cog
        self._register_commands()

    def _register_commands(self) -> None:
        @app_commands.command(name="overview", description="Show top-level categories and example commands.")
        async def overview(interaction: discord.Interaction) -> None:
            await self._cog._slash_help_overview(interaction)

        @app_commands.command(name="category", description="Describe the commands available in a category.")
        @app_commands.describe(name="Category name, e.g. Games, Moderation, Admin.")
        async def category(interaction: discord.Interaction, name: str) -> None:
            await self._cog._slash_help_category(interaction, name)

        @app_commands.command(name="admin", description="Detailed help for admin commands.")
        async def admin(interaction: discord.Interaction) -> None:
            await self._cog._slash_help_admin(interaction)

        self.add_command(overview)
        self.add_command(category)
        self.add_command(admin)