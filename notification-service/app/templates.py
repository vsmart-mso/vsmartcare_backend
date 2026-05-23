"""Backward-compatible entry point — use app.email_templates for new code."""

from .email_templates import render_email

__all__ = ["render_email"]
