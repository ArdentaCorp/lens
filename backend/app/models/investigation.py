import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InvestigationRecord(Base):
    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(String, nullable=False)
    matched_image_ids: Mapped[str | None] = mapped_column(
        String, nullable=True)  # JSON text
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
