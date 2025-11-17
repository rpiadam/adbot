"""Discord command cogs bundled with the relay bot."""

from .admin import AdminCog
from .chocolate import ChocolateCog
from .configuration import ConfigurationCog
from .features import FeaturesCog
from .flood import FloodCog
from .games import GamesCog
from .help import HelpCog
from .moderation import ModerationCog
from .monitoring import MonitoringCog
from .music import MusicCog
from .pota import POTACog
from .rss import RSSCog
from .welcome import WelcomeCog
from .football import FootballCog
from .znc import ZNCCog

__all__ = [
    "AdminCog",
    "ChocolateCog",
    "ConfigurationCog",
    "FeaturesCog",
    "FloodCog",
    "FootballCog",
    "GamesCog",
    "HelpCog",
    "ModerationCog",
    "MonitoringCog",
    "MusicCog",
    "POTACog",
    "RSSCog",
    "WelcomeCog",
    "ZNCCog",
]

