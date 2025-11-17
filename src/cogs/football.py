from __future__ import annotations

from typing import Optional, TYPE_CHECKING, List

import discord
from discord import app_commands
from discord.ext import commands

from ..models import FootballEvent

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class FootballCog(commands.Cog):
    """Slash command helpers for posting Football Nation style updates."""

    football = app_commands.Group(
        name="football",
        description="Manage and post Football Nation style match updates.",
    )

    COMPETITION_CHOICES: List[app_commands.Choice[str]] = [
        app_commands.Choice(name="Premier League", value="Premier League"),
        app_commands.Choice(name="La Liga", value="La Liga"),
        app_commands.Choice(name="Serie A", value="Serie A"),
        app_commands.Choice(name="Bundesliga", value="Bundesliga"),
        app_commands.Choice(name="MLS", value="MLS"),
        app_commands.Choice(name="UEFA Champions League", value="UEFA Champions League"),
    ]

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator

    async def _assert_relay_channel(self, interaction: discord.Interaction) -> bool:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Please run this command in a server text channel.",
                ephemeral=True,
            )
            return False
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.",
                ephemeral=True,
            )
            return False
        return True

    async def _resolve_defaults(self) -> dict[str, str]:
        defaults = await self.coordinator.config_store.get_football_defaults()
        settings = self.coordinator.settings
        return {
            "competition": defaults.get("competition") or settings.football_default_competition or "",
            "team": defaults.get("team") or settings.football_default_team or "",
            "opponent": defaults.get("opponent") or "",
            "prefix": defaults.get("webhook_summary_prefix") or "",
        }

    @football.command(name="post", description="Post a Football Nation style match update.")
    @app_commands.choices(competition_choice=COMPETITION_CHOICES)
    @app_commands.describe(
        title="Headline for the update.",
        status="Match status (e.g. Goal, Half-time).",
        competition_choice="Select a competition from common leagues.",
        competition_custom="Custom competition/league name if not in the list.",
        team="Team the update relates to. Leave blank for default.",
        opponent="Opposing team. Leave blank for default.",
        minute="Match minute.",
        score_home="Home score.",
        score_away="Away score.",
        commentary="Short commentary or note.",
    )
    async def football_post(
        self,
        interaction: discord.Interaction,
        title: Optional[str] = None,
        status: Optional[str] = None,
        competition_choice: Optional[str] = None,
        competition_custom: Optional[str] = None,
        team: Optional[str] = None,
        opponent: Optional[str] = None,
        minute: Optional[int] = None,
        score_home: Optional[int] = None,
        score_away: Optional[int] = None,
        commentary: Optional[str] = None,
    ) -> None:
        if not await self._assert_relay_channel(interaction):
            return

        defaults = await self._resolve_defaults()
        competition = competition_custom or competition_choice or defaults["competition"] or None
        team = team or defaults["team"] or None
        opponent = opponent or defaults["opponent"] or None

        payload = FootballEvent(
            title=title,
            status=status,
            competition=competition,
            team=team,
            opponent=opponent,
            minute=minute,
            score_home=score_home,
            score_away=score_away,
            commentary=commentary,
        )
        summary = payload.to_summary(self.coordinator.settings)
        prefix = defaults["prefix"]
        if prefix:
            summary = f"{prefix.strip()} {summary}".strip()

        await self.coordinator.announce_football_event(summary)

        embed = discord.Embed(
            title=title or status or "Match Update",
            description=commentary or "Update posted to the relay.",
            colour=discord.Colour.dark_green(),
        )
        if competition:
            embed.add_field(name="Competition", value=competition, inline=True)
        if status:
            embed.add_field(name="Status", value=status, inline=True)
        if minute:
            embed.add_field(name="Minute", value=f"{minute}'", inline=True)
        if team or opponent:
            embed.add_field(
                name="Fixture",
                value=f"{team or '?'} vs {opponent or '?'}",
                inline=False,
            )
        if score_home is not None or score_away is not None:
            embed.add_field(
                name="Score",
                value=f"{score_home if score_home is not None else 0} - {score_away if score_away is not None else 0}",
                inline=False,
            )
        await interaction.response.send_message("Football update delivered to relay.", embed=embed, ephemeral=True)

    @football.command(name="config", description="Show or update default football values.")
    @app_commands.choices(competition_choice=COMPETITION_CHOICES)
    @app_commands.describe(
        competition_choice="Select a default competition from common leagues.",
        competition="Custom competition/league name.",
        team="Default home team name.",
        opponent="Default opponent name.",
        summary_prefix="Text prefixed before every summary.",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def football_config(
        self,
        interaction: discord.Interaction,
        competition_choice: Optional[str] = None,
        competition: Optional[str] = None,
        team: Optional[str] = None,
        opponent: Optional[str] = None,
        summary_prefix: Optional[str] = None,
    ) -> None:
        if (
            competition_choice is None
            and competition is None
            and team is None
            and opponent is None
            and summary_prefix is None
        ):
            defaults = await self._resolve_defaults()
            embed = discord.Embed(
                title="Football Defaults",
                colour=discord.Colour.blurple(),
            )
            embed.add_field(name="Competition", value=defaults["competition"] or "Unset", inline=False)
            embed.add_field(name="Team", value=defaults["team"] or "Unset", inline=False)
            embed.add_field(name="Opponent", value=defaults["opponent"] or "Unset", inline=False)
            embed.add_field(name="Summary Prefix", value=defaults["prefix"] or "Unset", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        chosen_competition = competition or competition_choice

        updated = await self.coordinator.config_store.update_football_defaults(
            competition=chosen_competition,
            team=team,
            opponent=opponent,
            webhook_summary_prefix=summary_prefix,
        )
        embed = discord.Embed(
            title="Football Defaults Updated",
            colour=discord.Colour.green(),
        )
        embed.add_field(name="Competition", value=updated.get("competition", "Unset"), inline=False)
        embed.add_field(name="Team", value=updated.get("team", "Unset"), inline=False)
        embed.add_field(name="Opponent", value=updated.get("opponent", "Unset"), inline=False)
        embed.add_field(name="Summary Prefix", value=updated.get("webhook_summary_prefix", "Unset"), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @football.command(name="reset", description="Clear saved football defaults.")
    @app_commands.default_permissions(manage_guild=True)
    async def football_reset(self, interaction: discord.Interaction) -> None:
        await self.coordinator.config_store.clear_football_defaults()
        await interaction.response.send_message(
            "Football defaults cleared. The command will revert to environment values.",
            ephemeral=True,
        )
