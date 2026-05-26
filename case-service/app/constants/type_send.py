"""รหัส type_send — ประเภทการส่งข้อมูลออกระบบ (ตาราง type_send)."""

from typing import Final, Literal

# ส่งต่อเข้าหระทรวง
TYPE_SEND_MINISTRY: Final[int] = 1
# ส่งต่อ MSO logbook
TYPE_SEND_LOGBOOK: Final[int] = 2

MsoForwardChannel = Literal["ministry", "logbook"]

CHANNEL_TO_TYPE_SEND_ID: dict[MsoForwardChannel, int] = {
    "ministry": TYPE_SEND_MINISTRY,
    "logbook": TYPE_SEND_LOGBOOK,
}

TYPE_SEND_ID_TO_CHANNEL: dict[int, MsoForwardChannel] = {
    TYPE_SEND_MINISTRY: "ministry",
    TYPE_SEND_LOGBOOK: "logbook",
}
