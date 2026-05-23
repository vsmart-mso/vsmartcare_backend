from __future__ import annotations

from ..branding import msdhs_logo_cid_src
from ..loader import fill, load_html
from .context import WelfareStatusContext

_HEADER_TITLE = "แจ้งอัปเดตสถานะคำร้องสวัสดิการ"

_FOOTER_TEXT = "ขอแสดงความนับถือ"
_FRAGMENT_DIR = "welfare_status_updated/fragments"


def _optional_fragment(fragment_name: str, **values: str) -> str:
    template = load_html(f"{_FRAGMENT_DIR}/{fragment_name}")
    return fill(template, **values)


def build_html_body(ctx: WelfareStatusContext, subject: str) -> str:
    box = ctx.status_box
    content = fill(
        load_html("welfare_status_updated/content.html"),
        greeting_name=ctx.greeting_name,
        status_label=ctx.status_label,
        status_bg_color=box.background,
        status_border_color=box.border,
        status_accent_color=box.accent,
        status_label_color=box.label,
        case_ref_block=_optional_fragment("case_ref.html", case_ref=ctx.case_ref)
        if ctx.case_ref
        else "",
        remarks_block=_optional_fragment("remarks.html", remarks=ctx.remarks)
        if ctx.remarks
        else "",
        tracking_block=_optional_fragment("tracking_button.html", tracking_url=ctx.tracking_url)
        if ctx.tracking_url
        else "",
        tracking_url=ctx.tracking_url,
    )

    return fill(
        load_html("layout.html"),
        title=subject,
        logo_url=msdhs_logo_cid_src(),
        header_title=_HEADER_TITLE,
        content=content,
        footer_text=_FOOTER_TEXT,
    )
