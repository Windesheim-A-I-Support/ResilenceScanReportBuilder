"""
email_tracker.py — stub (full implementation: Milestone 5)
Tracks per-recipient email send status, persisted to email_tracker.json.
"""


class EmailTracker:
    """Tracks which recipients have been sent their report."""

    def import_from_csv(self, path: str) -> tuple:
        """Import recipients from CSV. Returns (imported, skipped)."""
        return 0, 0

    def get_statistics(self) -> dict:
        """Return send statistics."""
        return {"total": 0, "sent": 0, "pending": 0, "failed": 0}

    def mark_sent(self, company: str, person: str) -> None:
        """Mark a recipient as sent."""

    def mark_pending(self, company: str, person: str) -> None:
        """Reset a recipient to pending."""
