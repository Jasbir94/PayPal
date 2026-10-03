"""Portable account and payment storage definitions for later repositories."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class AccountRecord(Base):
    __tablename__ = 'accounts'
    account_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fraud_report_count: Mapped[int] = mapped_column(Integer, default=0)
    is_known_mule: Mapped[bool] = mapped_column(Boolean, default=False)

class TransactionRecord(Base):
    __tablename__ = 'transactions'
    transaction_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey('accounts.account_id'))
    receiver_id: Mapped[str] = mapped_column(ForeignKey('accounts.account_id'))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    device_id: Mapped[str] = mapped_column(String(80))
    payment_type: Mapped[str] = mapped_column(String(40))
    first_time_recipient: Mapped[bool] = mapped_column(Boolean)
    payment_reason: Mapped[str] = mapped_column(String(40))
