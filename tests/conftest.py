"""
Shared pytest fixtures for BankFlow tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest

from bankflow.config import DatabaseConfig, get_settings
from bankflow.generator.defects import DefectConfig
from bankflow.generator.generator import SyntheticDataGenerator


@pytest.fixture
def tmp_dataset_dir(tmp_path: Path) -> Path:
    """Fixture providing a temporary directory for generated CSV datasets."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def clean_dataset_dir(tmp_dataset_dir: Path) -> Path:
    """Fixture generating a small, clean synthetic dataset in a temp directory."""
    generator = SyntheticDataGenerator(seed=42, defect_config=DefectConfig.clean())
    generator.export_all(
        output_dir=tmp_dataset_dir,
        num_branches=3,
        num_customers=10,
        num_accounts=15,
        num_transactions=50,
    )
    return tmp_dataset_dir


@pytest.fixture
def defective_dataset_dir(tmp_path: Path) -> Path:
    """Fixture generating a synthetic dataset with standard injected defects."""
    defect_dir = tmp_path / "defective_data"
    defect_dir.mkdir(parents=True, exist_ok=True)
    generator = SyntheticDataGenerator(seed=42, defect_config=DefectConfig.standard_test_defects())
    generator.export_all(
        output_dir=defect_dir,
        num_branches=3,
        num_customers=10,
        num_accounts=15,
        num_transactions=50,
    )
    return defect_dir


@pytest.fixture
def test_db_config() -> DatabaseConfig:
    """Return the configured test database settings."""
    return get_settings().test_db
