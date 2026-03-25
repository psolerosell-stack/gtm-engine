import json
import uuid
from typing import Any, Dict, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = structlog.get_logger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        table_name: str,
        record_id: uuid.UUID,
        operation: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        entry = AuditLog(
            table_name=table_name,
            record_id=record_id,
            operation=operation,
            old_values=json.dumps(old_values, default=str) if old_values is not None else None,
            new_values=json.dumps(new_values, default=str) if new_values is not None else None,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
        )
        self.db.add(entry)
        # Note: caller is responsible for committing the enclosing transaction
        logger.debug(
            "audit_log_created",
            table=table_name,
            record_id=str(record_id),
            operation=operation,
            user=user_email,
        )
        return entry


def _model_to_dict(obj: Any) -> Dict[str, Any]:
    """Shallow-convert a SQLAlchemy mapped instance to a plain dict for auditing."""
    result = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name, None)
        result[col.name] = val
    return result
