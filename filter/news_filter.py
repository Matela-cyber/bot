from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pytz
import requests
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger(__name__)

HIGH_IMPACT_EVENTS = [
    "FOMC",
    "Non-Farm Payrolls",
    "CPI",
    "GDP",
    "ECB Rate Decision",
    "BOE Rate Decision",
    "SNB Rate Decision",
    "RBA Rate Decision",
    "Federal Reserve Rate Decision",
    "European Central Bank Rate Decision",
    "Bank of England Rate Decision",
    "NFP",
    "Fed Chair Speech",
    "ECB Press Conference",
]

MEDIUM_IMPACT_EVENTS = [
    "PPI",
    "Retail Sales",
    "Consumer Confidence",
    "PMI",
    "Jobless Claims",
]

FOREXFACTORY_CALENDAR_URL = "https://www.forexfactory.com/calendar.php"


class NewsFilter:
    """Filter that blocks or reduces risk around economic news events."""

    def fetch_calendar(self, date: str | None = None) -> list[dict[str, Any]]:
        """Fetch the economic calendar for a given date."""
        if date is None:
            date = datetime.now(pytz.UTC).date().isoformat()

        events = self._fetch_with_forexfactory(date)
        if events is not None:
            return events

        logger.warning("NewsFilter: falling back to safe empty calendar")
        return []

    def _fetch_with_forexfactory(self, date: str) -> list[dict[str, Any]] | None:
        """Attempt to parse ForexFactory calendar HTML."""
        try:
            response = requests.get(FOREXFACTORY_CALENDAR_URL, timeout=10)
            response.raise_for_status()
            return self._parse_calendar(response.text, date)
        except Exception as exc:
            logger.warning("NewsFilter: failed to fetch ForexFactory calendar: %s", exc)
            return None

    def _parse_calendar(self, html: str, expected_date: str) -> list[dict[str, Any]]:
        """Parse ForexFactory calendar HTML into event dictionaries."""
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("#calendar .calendar__row") or soup.select(".calendar__row")
        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                date_cell = row.select_one(".calendar__date")
                time_cell = row.select_one(".calendar__time")
                currency_cell = row.select_one(".calendar__currency")
                impact_cell = row.select_one(".calendar__impact")
                event_cell = row.select_one(".calendar__event")
                if not (date_cell and time_cell and currency_cell and impact_cell and event_cell):
                    continue

                event_date = date_cell.get_text(strip=True)
                event_time = time_cell.get_text(strip=True)
                currency = currency_cell.get_text(strip=True)
                impact_value = impact_cell.get("title", impact_cell.get_text(strip=True))
                impact = str(impact_value).strip() if impact_value else ""
                event_name = event_cell.get_text(strip=True)

                if event_date != expected_date:
                    continue

                events.append(
                    {
                        "date": event_date,
                        "time": event_time,
                        "currency": currency,
                        "impact": impact,
                        "event": event_name,
                    }
                )
            except Exception:
                continue
        return events

    def is_high_impact_news(self, current_time: datetime | None = None, lookahead_minutes: int = 30) -> dict[str, Any]:
        """Determine whether there is an upcoming high- or medium-impact event."""
        now = current_time.astimezone(pytz.UTC) if current_time is not None else datetime.now(pytz.UTC)
        calendar = self.fetch_calendar(now.date().isoformat())
        best_event: dict[str, Any] | None = None
        best_minutes = 9999
        best_impact: str | None = None

        for event in calendar:
            event_time = self._parse_event_datetime(event, now)
            if event_time is None:
                continue
            minutes_until = int((event_time - now).total_seconds() / 60)
            if minutes_until < 0:
                continue

            impact_level = event.get("impact", "Low").capitalize()
            if impact_level not in {"High", "Medium", "Low"}:
                impact_level = "Low"

            event_name = event.get("event", "")
            if event_name in HIGH_IMPACT_EVENTS:
                impact_level = "High"
            elif event_name in MEDIUM_IMPACT_EVENTS:
                impact_level = "Medium"

            if minutes_until <= lookahead_minutes and minutes_until < best_minutes:
                best_event = event
                best_minutes = minutes_until
                best_impact = impact_level

        if best_event is None:
            return {
                "halt": False,
                "reason": "no_upcoming_news",
                "impact": None,
                "event_name": "",
                "minutes_until": -1,
            }

        if best_impact == "High":
            return {
                "halt": True,
                "reason": f"high_impact_news_in_{best_minutes}_minutes",
                "impact": "High",
                "event_name": best_event.get("event", "unknown"),
                "minutes_until": best_minutes,
            }

        if best_impact == "Medium":
            return {
                "halt": False,
                "reason": f"medium_impact_news_in_{best_minutes}_minutes",
                "impact": "Medium",
                "event_name": best_event.get("event", "unknown"),
                "minutes_until": best_minutes,
            }

        return {
            "halt": False,
            "reason": "low_impact_news_only",
            "impact": "Low",
            "event_name": best_event.get("event", "unknown"),
            "minutes_until": best_minutes,
        }

    def _parse_event_datetime(self, event: dict[str, Any], now: datetime) -> datetime | None:
        """Convert event date/time to a timezone-aware datetime."""
        try:
            date_text = event.get("date", "")
            time_text = event.get("time", "")
            if not date_text or not time_text:
                return None
            event_ts = datetime.fromisoformat(f"{date_text}T{time_text}")
            if event_ts.tzinfo is None:
                event_ts = event_ts.replace(tzinfo=pytz.UTC)
            return event_ts.astimezone(pytz.UTC)
        except ValueError:
            return None

    def should_trade(self, current_time: datetime) -> tuple[bool, str]:
        """Decide whether trading should proceed based on upcoming news."""
        news_outcome = self.is_high_impact_news(current_time, settings.news_lookahead_minutes)
        impact = news_outcome.get("impact")

        if news_outcome["halt"] and settings.news_avoid_high_impact:
            reason = f"High-impact news in {news_outcome['minutes_until']} minutes: {news_outcome['event_name']}"
            logger.info("NewsFilter: %s", reason)
            return False, reason

        if impact == "Medium" and settings.news_avoid_medium_impact:
            reason = f"Medium-impact news in {news_outcome['minutes_until']} minutes: {news_outcome['event_name']}"
            logger.info("NewsFilter: %s", reason)
            return False, reason

        if impact == "Medium":
            reason = f"Medium-impact news in {news_outcome['minutes_until']} minutes: {news_outcome['event_name']} (reduce risk)"
            logger.info("NewsFilter: %s", reason)
            return True, reason

        logger.info("NewsFilter: No blocking news")
        return True, "No news"

    def get_risk_multiplier(self, current_time: datetime | None = None) -> float:
        """Return the risk multiplier depending on the latest news state."""
        news_outcome = self.is_high_impact_news(current_time, settings.news_lookahead_minutes)
        if news_outcome["halt"]:
            return 0.0
        if news_outcome.get("impact") == "Medium":
            return 0.5
        return 1.0
