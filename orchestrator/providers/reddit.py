from __future__ import annotations

from datetime import datetime, timedelta, timezone

import praw

from orchestrator.config import RedditConfig
from orchestrator.models import PostCandidate
from orchestrator.providers.base import SocialProvider


class RedditProvider(SocialProvider):
    name = "reddit"

    def __init__(self, config: RedditConfig):
        if not (config.client_id and config.client_secret and config.username and config.password):
            raise ValueError("Reddit credentials are missing. Set client_id/client_secret/username/password.")
        self.config = config
        self.client = praw.Reddit(
            client_id=config.client_id,
            client_secret=config.client_secret,
            username=config.username,
            password=config.password,
            user_agent=config.user_agent,
            check_for_async=False,
        )

    def discover_candidates(self, search_queries: list[str]) -> list[PostCandidate]:
        results: list[PostCandidate] = []
        seen_ids: set[str] = set()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.lookback_hours)
        subreddit_query = "+".join(self.config.subreddits)
        subreddit = self.client.subreddit(subreddit_query)

        for query in search_queries:
            for submission in subreddit.search(query=query, sort="new", time_filter="day", limit=self.config.limit_per_query):
                if submission.id in seen_ids:
                    continue
                seen_ids.add(submission.id)

                created = datetime.fromtimestamp(float(submission.created_utc), tz=timezone.utc)
                if created < cutoff:
                    continue
                if bool(getattr(submission, "locked", False)):
                    continue

                body = (submission.selftext or "").strip()
                results.append(
                    PostCandidate(
                        provider=self.name,
                        provider_post_id=submission.id,
                        permalink=f"https://reddit.com{submission.permalink}",
                        author=str(getattr(submission, "author", "unknown")),
                        title=(submission.title or "").strip(),
                        body=body[:5000],
                        created_utc=created,
                        metadata={
                            "subreddit": str(submission.subreddit),
                            "num_comments": int(getattr(submission, "num_comments", 0)),
                            "score": int(getattr(submission, "score", 0)),
                        },
                    )
                )

        return results

    def send_reply(self, provider_post_id: str, text: str, dry_run: bool = False) -> str:
        if dry_run:
            return f"[dry-run] reddit post={provider_post_id}"
        submission = self.client.submission(id=provider_post_id)
        comment = submission.reply(text)
        return f"https://reddit.com{comment.permalink}"
