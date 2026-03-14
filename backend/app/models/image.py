import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        Index("ix_images_created_at", "created_at"),
        Index("ix_images_source", "source"),
        Index("ix_images_phash", "phash"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    image_path: Mapped[str] = mapped_column(String, nullable=False)
    phash: Mapped[str | None] = mapped_column(String, nullable=True)
    exif_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    ingested_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    analysis: Mapped["ImageAnalysis | None"] = relationship(  # noqa: F821
        back_populates="image", uselist=False, cascade="all, delete-orphan"
    )
