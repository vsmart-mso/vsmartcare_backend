from __future__ import annotations

from .context import WelfareCaseSubmittedContext, build_subject_base


def build_subject(ctx: WelfareCaseSubmittedContext) -> str:
    subject = build_subject_base(ctx.submission_kind)
    if ctx.case_ref:
        subject += f" ({ctx.case_ref})"
    return subject
