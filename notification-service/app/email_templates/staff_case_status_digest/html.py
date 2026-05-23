from __future__ import annotations

from ..province_summary import province_total_html_block, province_total_plain_line
from ..branding import msdhs_logo_cid_src
from ..loader import fill, load_html
from .context import StaffDigestContext

_HEADER_TITLE = "สรุปคำร้องสวัสดิการรายวัน"
_FOOTER_TEXT = "ขอแสดงความนับถือ"


def build_html_body(ctx: StaffDigestContext, subject: str) -> str:
    province_line = ""
    if ctx.province_name:
        province_line = f" — จังหวัด<strong>{ctx.province_name}</strong>"
    if ctx.position:
        province_line += (
            f'<br/><span style="font-size:14px;color:#64748B;">ตำแหน่ง: {ctx.position}</span>'
        )

    content = fill(
        load_html("staff_case_status_digest/content.html"),
        greeting_name=ctx.greeting_name,
        digest_date=ctx.digest_date or "-",
        province_line=province_line,
        province_total_block=province_total_html_block(ctx.province_name, ctx.total_applicants),
        highlight_label=ctx.highlight_label,
        highlight_count=ctx.highlight_count_text,
        emergency_label=ctx.emergency_label,
        emergency_count=ctx.emergency_count_text,
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
