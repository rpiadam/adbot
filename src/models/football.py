from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from ..config import Settings


class FootballEvent(BaseModel):
    """Payload model for Football Nation webhook events."""

    title: Optional[str] = Field(None, description="Short headline for the event.")
    competition: Optional[str] = Field(None, description="Competition or league name.")
    team: Optional[str] = Field(None, description="Team this update relates to.")
    opponent: Optional[str] = Field(None, description="The opposing team, if relevant.")
    status: Optional[str] = Field(None, description="Match status, e.g. 'Kick-off', 'Half-time'.")
    minute: Optional[int] = Field(None, description="Match minute if applicable.")
    score_home: Optional[int] = Field(None, description="Home score.")
    score_away: Optional[int] = Field(None, description="Away score.")
    commentary: Optional[str] = Field(None, description="Free-text commentary or note.")
    occurred_at: Optional[datetime] = Field(None, description="UTC timestamp of when the event occurred.")

    def to_summary(self, settings: Settings) -> str:
        headline_parts: list[str] = []
        if self.minute is not None:
            headline_parts.append(f"{self.minute}'")

        icon = "⚽"
        status_text = self.status or self.title
        if status_text:
            headline_parts.append(f"{icon} {status_text}")
        elif headline_parts:
            headline_parts.append(icon)

        summary_lines: list[str] = []
        if headline_parts:
            summary_lines.append(" ".join(part for part in headline_parts if part))

        if self.title and self.title != self.status:
            summary_lines.append(self.title)

        if self.commentary:
            summary_lines.append(self.commentary)

        competition = self.competition or settings.football_default_competition
        if competition:
            summary_lines.append(f"🏆 {competition}")

        team = self.team or settings.football_default_team
        opponent = self.opponent
        if team or opponent:
            home_score = "?" if self.score_home is None else str(self.score_home)
            away_score = "?" if self.score_away is None else str(self.score_away)
            if opponent:
                summary_lines.append(f"{team or '?'} {home_score} - {away_score} {opponent}")
            else:
                summary_lines.append(f"{team or '?'} {home_score}")
        elif self.score_home is not None and self.score_away is not None:
            summary_lines.append(f"Score: {self.score_home} - {self.score_away}")

        if self.occurred_at:
            summary_lines.append(self.occurred_at.strftime("⏱ %Y-%m-%d %H:%M UTC"))

        if not summary_lines:
            summary_lines.append("⚽ Football Nation update")

        return "\n".join(summary_lines)
