# slash-based games cog
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Set, Tuple

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


@dataclass
class HangmanState:
    word: str
    guessed_letters: Set[str] = field(default_factory=set)
    wrong_letters: Set[str] = field(default_factory=set)
    remaining_attempts: int = 6

    def reveal(self) -> str:
        return " ".join(letter if letter in self.guessed_letters else "•" for letter in self.word)

    def is_complete(self) -> bool:
        return all(letter in self.guessed_letters for letter in self.word)


@dataclass
class TicTacToeState:
    players: Tuple[int, int]  # (starter, opponent)
    board: List[Optional[int]] = field(default_factory=lambda: [None] * 9)
    current_turn: int = 0  # index into players tuple

    def render(self) -> str:
        def _symbol(idx: int) -> str:
            mark = self.board[idx]
            if mark is None:
                return str(idx + 1)
            return "❌" if mark == self.players[0] else "⭕"

        rows = [" | ".join(_symbol(i + j * 3) for i in range(3)) for j in range(3)]
        return "\n---------\n".join(rows)

    def make_move(self, index: int, player_id: int) -> None:
        if self.board[index] is not None:
            raise ValueError("Cell already taken.")
        if player_id != self.players[self.current_turn]:
            raise ValueError("Not your turn.")
        self.board[index] = player_id
        self.current_turn = 1 - self.current_turn

    def winner(self) -> Optional[int]:
        combos = [
            (0, 1, 2),
            (3, 4, 5),
            (6, 7, 8),
            (0, 3, 6),
            (1, 4, 7),
            (2, 5, 8),
            (0, 4, 8),
            (2, 4, 6),
        ]
        for a, b, c in combos:
            if self.board[a] is not None and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    def is_draw(self) -> bool:
        return all(cell is not None for cell in self.board)


@dataclass(frozen=True)
class TriviaQuestion:
    prompt: str
    options: Tuple[str, str, str, str]
    answer_index: int


class GamesCog(commands.Cog):
    """Lightweight community games to keep the relay channel lively."""

    def __init__(self, coordinator: RelayCoordinator):
        self.coordinator = coordinator
        self._hangman_games: Dict[int, HangmanState] = {}
        self._tictactoe_games: Dict[int, TicTacToeState] = {}
        self._word_ladder_pairs: List[Tuple[str, str]] = [
            ("cat", "dog"),
            ("cold", "warm"),
            ("lead", "gold"),
            ("stone", "money"),
            ("brain", "heart"),
        ]
        self._trivia_bank: List[TriviaQuestion] = [
            TriviaQuestion(
                prompt="Which protocol does Discord use to deliver voice traffic?",
                options=("UDP", "TCP", "FTP", "SCP"),
                answer_index=0,
            ),
            TriviaQuestion(
                prompt="What is the default IRC port when using TLS?",
                options=("6667", "6697", "7000", "7331"),
                answer_index=1,
            ),
            TriviaQuestion(
                prompt="Which country hosted the first FIFA World Cup?",
                options=("Brazil", "France", "Uruguay", "England"),
                answer_index=2,
            ),
            TriviaQuestion(
                prompt="In computing, what does the acronym 'JSON' stand for?",
                options=("Java Source Object Notation", "JavaScript Object Notation", "Joined Schema Object Name", "JavaScript Online Notation"),
                answer_index=1,
            ),
        ]

    async def _assert_relay_channel(self, interaction: discord.Interaction) -> bool:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Games can only be used in guild text channels.",
                ephemeral=True,
            )
            return False
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.",
                ephemeral=True,
            )
            return False
        return True

    async def _deduct_wager(self, interaction: discord.Interaction, wager: int) -> Optional[int]:
        if wager <= 0:
            async def _respond() -> None:
                await interaction.response.send_message("Place a wager greater than zero credits.", ephemeral=True)

            if interaction.response.is_done():
                await interaction.followup.send("Place a wager greater than zero credits.", ephemeral=True)
            else:
                await _respond()
            return None

        balance = await self.coordinator.config_store.get_credits(interaction.user.id)
        if balance < wager:
            message = (
                f"You only have {balance} credits available. "
                "Ask an admin to top you up with `/reward`."
            )
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return None

        await self.coordinator.config_store.add_credits(interaction.user.id, -wager)
        return balance - wager

    async def _build_economy_embed(
        self,
        *,
        title: str,
        description: str,
        wager: int,
        payout: int,
        balance: int,
        footer: Optional[str] = None,
        colour: Optional[discord.Colour] = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            colour=colour or (discord.Colour.gold() if payout > 0 else discord.Colour.red()),
        )
        embed.add_field(name="Wager", value=f"{wager} credits", inline=True)
        embed.add_field(name="Payout", value=f"{payout} credits", inline=True)
        embed.add_field(name="New Balance", value=f"{balance} credits", inline=True)
        if footer:
            embed.set_footer(text=footer)
        return embed

    @app_commands.command(
        name="coinflip",
        description="Flip a coin for a chance to double your wager.",
    )
    @app_commands.describe(
        call="Pick your side of the coin.",
        wager="Credits to stake on the flip (default 10).",
    )
    async def coin_flip(
        self,
        interaction: discord.Interaction,
        call: Literal["Heads", "Tails"] = "Heads",
        wager: app_commands.Range[int, 1, 1_000_000] = 10,
    ) -> None:
        if not await self._assert_relay_channel(interaction):
            return

        if await self._deduct_wager(interaction, wager) is None:
            return

        result = random.choice(["Heads", "Tails"])
        win = call.lower() == result.lower()
        payout = wager * 2 if win else 0
        if win:
            await self.coordinator.config_store.add_credits(interaction.user.id, payout)
        balance = await self.coordinator.config_store.get_credits(interaction.user.id)

        embed = await self._build_economy_embed(
            title="🪙 Coin Flip",
            description=(
                f"You called **{call}**.\n"
                f"The coin landed on **{result}**.\n"
                f"{'You win!' if win else 'House wins this round.'}"
            ),
            wager=wager,
            payout=payout,
            balance=balance,
            footer="Payouts: Correct call = 2x wager, Incorrect call = 0.",
            colour=discord.Colour.gold() if win else discord.Colour.dark_grey(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roll", description="Roll a die with the given number of sides.")
    @app_commands.describe(sides="Number of sides (between 2 and 1000).")
    async def roll(self, interaction: discord.Interaction, sides: app_commands.Range[int, 2, 1000] = 6) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        value = random.randint(1, sides)
        await interaction.response.send_message(f"🎲 Rolled a {sides}-sided die: **{value}**")

    @app_commands.command(name="pick", description="Pick a random option from a comma-separated list.")
    @app_commands.describe(options="Provide at least two choices separated by commas.")
    async def pick(self, interaction: discord.Interaction, options: str) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        choices = [choice.strip() for choice in options.split(",") if choice.strip()]
        if len(choices) < 2:
            await interaction.response.send_message(
                "Give me at least two choices separated by commas.",
                ephemeral=True,
            )
            return
        selection = random.choice(choices)
        await interaction.response.send_message(f"🤔 I choose: **{selection}**")

    hangman = app_commands.Group(name="hangman", description="Play a cooperative game of hangman.")

    @hangman.command(name="start", description="Begin a hangman round.")
    async def hangman_start(self, interaction: discord.Interaction) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)
        if channel.id in self._hangman_games:
            await interaction.response.send_message("A hangman game is already in progress here.", ephemeral=True)
            return

        word = random.choice([
            "relay",
            "discord",
            "python",
            "webhook",
            "football",
            "network",
            "monitor",
            "bridge",
            "uptime",
            "guild",
        ])
        state = HangmanState(word=word)
        self._hangman_games[channel.id] = state
        await interaction.response.send_message(
            f"🎯 Hangman started! Word: `{state.reveal()}`\n"
            "Use `/hangman guess <letter>` to play. You have 6 incorrect guesses.",
        )

    @hangman.command(name="guess", description="Guess a letter for the active hangman game.")
    @app_commands.describe(letter="Single letter to guess.")
    async def hangman_guess(self, interaction: discord.Interaction, letter: str) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)
        state = self._hangman_games.get(channel.id)
        if state is None:
            await interaction.response.send_message("No hangman game is running. Start one with `/hangman start`.", ephemeral=True)
            return

        letter = letter.strip().lower()
        if len(letter) != 1 or letter not in string.ascii_lowercase:
            await interaction.response.send_message("Please guess a single alphabetical character.", ephemeral=True)
            return

        if letter in state.guessed_letters or letter in state.wrong_letters:
            await interaction.response.send_message("That letter has already been guessed.", ephemeral=True)
            return

        if letter in state.word:
            state.guessed_letters.add(letter)
            if state.is_complete():
                del self._hangman_games[channel.id]
                await interaction.response.send_message(f"🎉 Correct! The word was **{state.word}**. Hangman cleared!")
            else:
                await interaction.response.send_message(f"✅ Nice! `{state.reveal()}`\nWrong guesses: {', '.join(sorted(state.wrong_letters)) or 'none'}")
        else:
            state.wrong_letters.add(letter)
            state.remaining_attempts -= 1
            if state.remaining_attempts <= 0:
                del self._hangman_games[channel.id]
                await interaction.response.send_message(
                    f"💀 No more attempts! The word was **{state.word}**.",
                )
            else:
                await interaction.response.send_message(
                    f"❌ Not there. `{state.reveal()}`\n"
                    f"Wrong guesses: {', '.join(sorted(state.wrong_letters)) or 'none'}\n"
                    f"Lives remaining: {state.remaining_attempts}",
                )

    @hangman.command(name="status", description="Show the current hangman board.")
    async def hangman_status(self, interaction: discord.Interaction) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)
        state = self._hangman_games.get(channel.id)
        if state is None:
            await interaction.response.send_message("No hangman game is in progress.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"`{state.reveal()}`\nWrong guesses: {', '.join(sorted(state.wrong_letters)) or 'none'}\nLives remaining: {state.remaining_attempts}",
            ephemeral=True,
        )

    tictactoe = app_commands.Group(
        name="tictactoe",
        description="Challenge someone to tic-tac-toe.",
    )

    @tictactoe.command(name="start", description="Start a new tic-tac-toe match against another member.")
    @app_commands.describe(opponent="The member to challenge.")
    async def tictactoe_start(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        if opponent.bot:
            await interaction.response.send_message("Pick a human opponent for tic-tac-toe.", ephemeral=True)
            return
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You cannot challenge yourself.", ephemeral=True)
            return

        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)
        if channel.id in self._tictactoe_games:
            await interaction.response.send_message("Finish the current tic-tac-toe game first.", ephemeral=True)
            return

        order = [interaction.user.id, opponent.id]
        random.shuffle(order)
        state = TicTacToeState(players=(order[0], order[1]))
        self._tictactoe_games[channel.id] = state

        first_player = interaction.guild.get_member(state.players[0])
        second_player = interaction.guild.get_member(state.players[1])
        await interaction.response.send_message(
            "🎮 Tic-Tac-Toe battle begins!\n"
            f"❌ {first_player.mention if first_player else 'Player 1'} goes first.\n"
            f"⭕ {second_player.mention if second_player else 'Player 2'} awaits their turn.\n"
            f"Board:\n```\n{state.render()}\n```",
        )

    @tictactoe.command(name="move", description="Claim a square in the active tic-tac-toe game.")
    @app_commands.describe(position="Choose a position 1-9, row by row.")
    async def tictactoe_move(
        self,
        interaction: discord.Interaction,
        position: app_commands.Range[int, 1, 9],
    ) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)
        state = self._tictactoe_games.get(channel.id)
        if state is None:
            await interaction.response.send_message("There is no tic-tac-toe game in progress.", ephemeral=True)
            return

        spot = position - 1
        try:
            state.make_move(spot, interaction.user.id)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        winner_id = state.winner()
        board_render = state.render()
        if winner_id is not None:
            del self._tictactoe_games[channel.id]
            winner_member = interaction.guild.get_member(winner_id)
            await interaction.response.send_message(
                f"🏆 {winner_member.mention if winner_member else 'A player'} wins!\n```\n{board_render}\n```"
            )
            return

        if state.is_draw():
            del self._tictactoe_games[channel.id]
            await interaction.response.send_message(
                f"🤝 It's a draw!\n```\n{board_render}\n```"
            )
            return

        next_player_id = state.players[state.current_turn]
        next_player = interaction.guild.get_member(next_player_id)
        await interaction.response.send_message(
            f"Move recorded.\n```\n{board_render}\n```\n"
            f"It's now {next_player.mention if next_player else 'the next player'}'s turn.",
        )

    @tictactoe.command(name="stop", description="Cancel the current tic-tac-toe game.")
    async def tictactoe_stop(self, interaction: discord.Interaction) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)
        if channel.id not in self._tictactoe_games:
            await interaction.response.send_message("No tic-tac-toe game to stop.", ephemeral=True)
            return
        del self._tictactoe_games[channel.id]
        await interaction.response.send_message("🛑 Tic-tac-toe game cancelled.")

    @app_commands.command(
        name="slots",
        description="Spin the reels and earn credits from matching symbols.",
    )
    @app_commands.describe(wager="Credits to stake on this spin (default 25).")
    async def slots(
        self,
        interaction: discord.Interaction,
        wager: app_commands.Range[int, 1, 1_000_000] = 25,
    ) -> None:
        if not await self._assert_relay_channel(interaction):
            return

        if await self._deduct_wager(interaction, wager) is None:
            return

        symbols = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎"]
        reels = [random.choice(symbols) for _ in range(3)]
        unique = set(reels)
        multiplier: int
        if len(unique) == 1:
            result = "Jackpot! Triple match!"
            multiplier = 10
        elif len(unique) == 2:
            result = "Nice! Two of a kind."
            multiplier = 3
        else:
            result = "No match this time."
            multiplier = 0

        payout = wager * multiplier
        if payout:
            await self.coordinator.config_store.add_credits(interaction.user.id, payout)
        balance = await self.coordinator.config_store.get_credits(interaction.user.id)

        embed = await self._build_economy_embed(
            title="🎰 Slot Machine",
            description=f"{' | '.join(reels)} → {result}",
            wager=wager,
            payout=payout,
            balance=balance,
            footer="Paytable: Triple match = 10x • Double match = 3x • Mixed = 0x",
            colour=discord.Colour.gold() if payout else discord.Colour.dark_grey(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="gamble", description="Wager an amount of credits for a chance to double it.")
    @app_commands.describe(amount="Amount to wager (must be a positive integer).")
    async def gamble(self, interaction: discord.Interaction, amount: int = 10) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        if amount <= 0:
            await interaction.response.send_message("Bet at least 1 credit to play.", ephemeral=True)
            return

        balance = await self.coordinator.config_store.get_credits(interaction.user.id)
        if balance < amount:
            await interaction.response.send_message(
                f"You only have {balance} credits. Use `/reward` to request more.",
                ephemeral=True,
            )
            return

        await self.coordinator.config_store.add_credits(interaction.user.id, -amount)
        win = random.random() < 0.48
        payout = amount * 2 if win else 0
        if win:
            await self.coordinator.config_store.add_credits(interaction.user.id, payout)
        new_balance = await self.coordinator.config_store.get_credits(interaction.user.id)

        embed = discord.Embed(
            title="🎰 Gamble Result",
            colour=discord.Colour.gold() if win else discord.Colour.red(),
            description="Lady Luck smiled on you!" if win else "House wins this round.",
        )
        embed.add_field(name="Wager", value=str(amount))
        embed.add_field(name="Payout", value=str(payout))
        embed.add_field(name="New Balance", value=str(new_balance))
        outcome = "won" if win else "lost"
        await interaction.response.send_message(
            f"{interaction.user.mention} {outcome} their bet.",
            embed=embed,
        )

    @app_commands.command(name="wordladder", description="Get a random word ladder challenge.")
    async def word_ladder(self, interaction: discord.Interaction) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        start, end = random.choice(self._word_ladder_pairs)
        await interaction.response.send_message(
            "🪜 **Word Ladder Challenge**\n"
            f"Transform **{start.upper()}** into **{end.upper()}** changing one letter at a time, "
            "with each step being a valid word. Good luck!"
        )

    @app_commands.command(name="trivia", description="Answer a multiple choice trivia question.")
    async def trivia(self, interaction: discord.Interaction) -> None:
        if not await self._assert_relay_channel(interaction):
            return
        question = random.choice(self._trivia_bank)

        class TriviaView(discord.ui.View):
            def __init__(self, *, owner_id: int, answer_index: int) -> None:
                super().__init__(timeout=30)
                self.owner_id = owner_id
                self.answer_index = answer_index
                self.answered = False

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user.id != self.owner_id:
                    await interaction.response.send_message("Only the person who called `/trivia` can answer this question.", ephemeral=True)
                    return False
                return True

            async def on_timeout(self) -> None:
                for child in self.children:
                    if isinstance(child, discord.ui.Button):
                        child.disabled = True

        view = TriviaView(owner_id=interaction.user.id, answer_index=question.answer_index)

        for idx, option in enumerate(question.options):
            style = discord.ButtonStyle.secondary

            class TriviaButton(discord.ui.Button):
                def __init__(self, label: str, index: int) -> None:
                    super().__init__(label=label, style=style)
                    self.index = index

                async def callback(self, interaction: discord.Interaction) -> None:
                    assert isinstance(self.view, TriviaView)
                    view: TriviaView = self.view
                    if view.answered:
                        await interaction.response.send_message("This question has already been answered.", ephemeral=True)
                        return
                    view.answered = True
                    for child in view.children:
                        child.disabled = True
                        if isinstance(child, TriviaButton) and child.index == view.answer_index:
                            child.style = discord.ButtonStyle.success
                        elif isinstance(child, TriviaButton):
                            child.style = discord.ButtonStyle.danger if child.index == self.index else child.style

                    if self.index == view.answer_index:
                        await interaction.response.edit_message(content="✅ Correct! Nice work.", view=view)
                    else:
                        correct = question.options[view.answer_index]
                        await interaction.response.edit_message(content=f"❌ Not quite. Correct answer: **{correct}**", view=view)

            view.add_item(TriviaButton(label=f"{idx + 1}. {option}", index=idx))

        embed = discord.Embed(
            title="Trivia Time!",
            description=question.prompt,
            colour=discord.Colour.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="credits", description="Check how many gamble credits you have.")
    async def credits(self, interaction: discord.Interaction) -> None:
        balance = await self.coordinator.config_store.get_credits(interaction.user.id)
        await interaction.response.send_message(
            f"{interaction.user.mention}, you have **{balance}** credits available.",
            ephemeral=True,
        )

    @app_commands.command(name="reward", description="Grant gamble credits to a member.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(member="Member to reward.", amount="Number of credits to grant.", overwrite="Set an exact balance instead of adding.")
    async def reward(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1, 1_000_000] = 100,
        overwrite: Optional[bool] = False,
    ) -> None:
        if not await self._assert_relay_channel(interaction):
            return

        if member.bot:
            await interaction.response.send_message("Bots do not need credits.", ephemeral=True)
            return

        if overwrite:
            new_balance = await self.coordinator.config_store.set_credits(member.id, amount)
            action = "set"
        else:
            new_balance = await self.coordinator.config_store.add_credits(member.id, amount)
            action = "granted"

        await interaction.response.send_message(
            f"{interaction.user.mention} {action} {amount} credits to {member.mention}. New balance: **{new_balance}**.",
            ephemeral=True,
        )

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            return
        message = "Something went wrong running that game."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


