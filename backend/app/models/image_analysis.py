import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ImageAnalysis(Base):
    __tablename__ = "image_analyses"
    __table_args__ = (
        Index("ix_analyses_image_id", "image_id", unique=True),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("images.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    detected_objects: Mapped[str | None] = mapped_column(
        String, nullable=True)  # JSON text
    attributes: Mapped[str | None] = mapped_column(
        String, nullable=True)  # JSON text
    search_text: Mapped[str | None] = mapped_column(
        Text, nullable=True)  # Clean plaintext for FTS
    embedding: Mapped[str | None] = mapped_column(
        Text, nullable=True)  # JSON list of floats
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    analyzed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    image: Mapped["Image"] = relationship(back_populates="analysis")  # noqa: F821
