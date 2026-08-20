"""
Tests for Database Base Model, Audit Timestamps, and Rollback Integrity.
"""
import pytest
from sqlalchemy import Column, String
from app.core.database import BaseModel, check_db_health


class DummyTestModel(BaseModel):
    __tablename__ = "dummy_test_items"
    name = Column(String(50), nullable=False)


def test_database_health_check():
    """Verify database connection ping function returns healthy status."""
    assert check_db_health() is True


def test_base_model_fields(db_session):
    """Verify BaseModel assigns UUID id, created_at, and updated_at automatically."""
    DummyTestModel.__table__.create(bind=db_session.bind, checkfirst=True)
    
    item = DummyTestModel(name="Test Patient")
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    
    assert item.id is not None
    assert len(item.id) == 36
    assert item.created_at is not None
    assert item.updated_at is not None
    assert item.name == "Test Patient"
