---
name: axion-module-development
description: Adding new modules to the Axion platform following established patterns. Each PRD produces 5 artifacts -- source module (src/<module>/), test file (tests/test_<module>.py), Streamlit dashboard (app/pages/<module>.py), Alembic migration (alembic/versions/XXX_*.py), and docs (docs/PRD-XX-*.md). Covers ORM model registration in src/db/models.py, migration chain linking, Streamlit dashboards with st.tabs(), pytest class-based organization, and known pitfalls.
metadata:
  author: axion-platform
  version: "1.0"
---

# Axion Module Development

## When to use this skill

Use this skill when you need to:
- Add a new module (PRD) to the Axion platform
- Understand the standard 5-artifact pattern (source, tests, dashboard, migration, docs)
- Register ORM models in the central models file
- Create and chain Alembic migrations correctly
- Build Streamlit dashboard pages with the standard tab layout
- Write pytest test files following the class-based organization
- Avoid known pitfalls (metadata reserved word, table name collisions, migration chain breaks)

## Step-by-step instructions

### 1. Module structure overview

Every new PRD produces exactly 5 artifacts:

```
src/<module_name>/              # Source module (Python package)
    __init__.py                 # Public API exports
    config.py                   # Enums, dataclasses, constants
    models.py                   # Domain model dataclasses
    <core_logic>.py             # Main implementation classes
tests/test_<module_name>.py     # Test file (class-based organization)
app/pages/<module_name>.py      # Streamlit dashboard page
alembic/versions/XXX_<name>.py  # Database migration
docs/PRD-XX-<title>.md          # PRD documentation
```

### 2. Create the source module

#### a. Module `__init__.py`

Export all public classes, functions, and constants:

```python
"""PRD-XXX: Module Title.

Brief description of what this module provides.

Example:
    from src.my_module import MyManager, MyConfig

    manager = MyManager()
    result = manager.process(data)
"""

from src.my_module.config import (
    MyEnum,
    MyConfig,
    DEFAULT_CONFIG,
)
from src.my_module.models import (
    MyDataModel,
    MyResult,
)
from src.my_module.manager import (
    MyManager,
)

__all__ = [
    "MyEnum",
    "MyConfig",
    "DEFAULT_CONFIG",
    "MyDataModel",
    "MyResult",
    "MyManager",
]
```

#### b. Configuration (`config.py`)

Use enums and dataclasses:

```python
"""PRD-XXX: Module Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class MyEnum(Enum):
    OPTION_A = "option_a"
    OPTION_B = "option_b"


@dataclass
class MyConfig:
    """Configuration for MyModule."""
    enabled: bool = True
    max_items: int = 100
    threshold: float = 0.5

DEFAULT_CONFIG = MyConfig()
```

#### c. Domain models (`models.py`)

Use dataclasses (not Pydantic) for domain models:

```python
"""PRD-XXX: Domain Models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class MyDataModel:
    """Represents a single item."""
    item_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    value: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
```

#### d. Core logic

Use classes with clear docstrings, type hints, and logging:

```python
"""PRD-XXX: Core logic implementation."""
import logging
from typing import Optional
from src.my_module.config import MyConfig, DEFAULT_CONFIG
from src.my_module.models import MyDataModel, MyResult

logger = logging.getLogger(__name__)

class MyManager:
    """Main manager class for the module."""

    def __init__(self, config: Optional[MyConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._items: list[MyDataModel] = []

    def process(self, data: dict) -> MyResult:
        """Process incoming data."""
        logger.info("Processing data: %s", data.get("id"))
        return MyResult(status="completed")
```

### 3. Register ORM models in `src/db/models.py`

All ORM models are registered centrally in `src/db/models.py` (~5280 lines). Add your models at the end of the file, following the pattern:

```python
# ── PRD-XXX: My Module ──────────────────────────────────────────────

class MyRecordBase(Base):
    """Stores my_module records."""
    __tablename__ = "my_module_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(64), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    value = Column(Float, nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

**IMPORTANT -- Known pitfalls:**

1. **`metadata` is reserved**: SQLAlchemy Base uses `metadata` internally. If your table has a metadata column, use an alias:

```python
# WRONG -- will conflict with SQLAlchemy
metadata = Column(Text, nullable=True)

# CORRECT -- use column alias
extra_metadata = Column("metadata", Text, nullable=True)
```

Known affected models: `RegimeStateRecord`, `LiquidityScoreRecord`, `DeploymentRecord`, `TenantAuditLogRecord`, `FeatureDefinitionRecord`.

2. **Table name collisions**: Check existing tablenames before creating yours. Known collision: `trade_executions` is used by `TradeExecution` (line ~284). PRD-135 uses `bot_trade_executions` prefix to avoid collision.

```python
# Check for existing table names
grep -r "__tablename__" src/db/models.py | grep "your_proposed_name"
```

3. **Duplicate ORM class names**: PRD-60 and PRD-142 both initially defined `NotificationPreferenceRecord`. Fixed by renaming PRD-142 to `AlertNetworkPreferenceRecord` with tablename `alert_network_preferences`.

### 4. Create the Alembic migration

Migrations are chained sequentially. Each migration's `down_revision` points to the previous migration number.

```python
"""PRD-XXX: my_module tables.

Revision ID: XXX
Revises: <previous_revision_number>
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = "XXX"
down_revision = "<previous_revision_number>"  # MUST match the prior migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "my_module_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("record_id", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_my_module_records_record_id", "my_module_records", ["record_id"])


def downgrade() -> None:
    op.drop_index("ix_my_module_records_record_id")
    op.drop_table("my_module_records")
```

**IMPORTANT -- Migration chain linking:**

The current chain is: `...161 -> 162 -> 163 -> 165 -> 166 -> 167 -> 170 -> 171 -> 172 -> 173 -> 174 -> 175 -> 176 -> 177 -> 178`

To find the latest migration for your `down_revision`:

```bash
# Find the highest-numbered migration
ls alembic/versions/ | sort -t_ -k1 -n | tail -5
```

**Known pitfall -- Migration chain breaks**: When multiple PRDs are developed in parallel (e.g., by background agents), they may independently set `down_revision` to the same value, creating a fork. Always provide explicit `down_revision` values to prevent this.

### 5. Create the Streamlit dashboard page

Dashboard pages go in `app/pages/<module_name>.py` and use `st.tabs()`:

```python
"""PRD-XXX: My Module Dashboard."""
import streamlit as st

st.set_page_config(page_title="My Module", layout="wide")
st.title("My Module Dashboard")

def render_overview_tab():
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Items", "42")
    col2.metric("Active", "38")
    col3.metric("Success Rate", "95.2%")
    col4.metric("Avg Value", "$1,234")

def render_config_tab():
    with st.form("config_form"):
        enabled = st.checkbox("Enabled", value=True)
        threshold = st.slider("Threshold", 0.0, 1.0, 0.5)
        if st.form_submit_button("Save"):
            st.success("Configuration saved!")

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Details", "Configuration", "History"])
with tab1:
    render_overview_tab()
with tab3:
    render_config_tab()
```

Standard pattern: 4 tabs (Overview, Details, Configuration, History) with `st.columns()` for metrics and `st.dataframe()` for tables.

### 6. Write tests

Tests go in `tests/test_<module_name>.py` using class-based organization:

```python
"""Tests for PRD-XXX: My Module."""
from src.my_module import MyManager, MyConfig, MyDataModel

class TestMyConfig:
    def test_default_config(self):
        config = MyConfig()
        assert config.enabled is True
        assert config.max_items == 100

class TestMyManager:
    def setup_method(self):
        self.manager = MyManager(config=MyConfig())

    def test_process_basic(self):
        result = self.manager.process({"id": "test1"})
        assert result.status == "completed"
```

**Conventions**: Use `setup_method()` (not `setUp`), group into classes by component, run with `python3 -m pytest tests/test_my_module.py -v`.

**Known testing pitfalls:**
- **Mock patch targets**: For `from foo import bar`, patch `importing_module.bar`. For lazy `import foo` inside methods, patch `foo.ClassName` directly.
- **Time-dependent tests**: Use `timeframe="1d"` to bypass market hours, `trade_type="swing"` to bypass EOD close.
- **Dict vs object fields**: `getattr(dict, "key")` fails silently. Use a helper that checks `isinstance(t, dict)` first.

### 7. Write documentation

Create `docs/PRD-XX-<title>.md` with sections: Overview, Architecture, Key Components, Usage Examples, Configuration, Database Schema, Testing.

## Code examples

### Complete module scaffold

Here is a minimal but complete example of adding a new module:

```bash
# 1. Create source directory
mkdir -p src/my_module

# 2. Create files (see templates above)
# src/my_module/__init__.py
# src/my_module/config.py
# src/my_module/models.py
# src/my_module/manager.py

# 3. Add ORM models to src/db/models.py (append at end)

# 4. Create migration
# alembic/versions/XXX_my_module.py

# 5. Create dashboard page
# app/pages/my_module.py

# 6. Create test file
# tests/test_my_module.py

# 7. Create documentation
# docs/PRD-XX-my-module.md

# 8. Run tests to verify
python3 -m pytest tests/test_my_module.py -v
```

### Bridge adapter pattern

Many PRDs integrate with existing modules using lightweight bridge adapters with lazy-loading:

```python
class MyBridge:
    def __init__(self, upstream=None):
        self._upstream = upstream or self._lazy_load()

    def adapt(self, data: dict) -> dict:
        if self._upstream is None:
            return data
        try:
            return self._upstream.process(data)
        except Exception as e:
            logger.warning("Bridge failed (non-fatal): %s", e)
            return data

    @staticmethod
    def _lazy_load():
        try:
            from src.existing_module import ExistingClass
            return ExistingClass()
        except ImportError:
            return None
```

## Key classes and methods

### Project structure reference

| Directory | Count | Purpose |
|-----------|-------|---------|
| `src/` | ~810 .py files | Source modules |
| `tests/` | 156+ .py files | Test files |
| `app/pages/` | 145 .py files | Streamlit dashboards |
| `alembic/versions/` | 178 .py files | Database migrations |
| `docs/` | 145+ .md files | PRD documentation |
| `src/db/models.py` | ~5280 lines | Central ORM models (218 tables) |

### Central files to modify

- `src/db/models.py` -- Add ORM table definitions
- `alembic/versions/` -- Add migration file with correct chain linking
- `app/nav_config.py` -- Add page to navigation (if needed)

## Common patterns

### Key codebase patterns

- **Lazy loading**: Use `try: from src.module import X; except ImportError: return None` to keep modules optional
- **Mutable defaults**: Use `field(default_factory=list)` in dataclasses, never bare `[]`
- **Thread safety**: Use `threading.RLock()` and `with self._lock:` for shared state
- **Logging**: `logger = logging.getLogger(__name__)` at module level

### Checklist for a new PRD

- [ ] Source module created in `src/<module>/` with `__init__.py`, `config.py`, `models.py`
- [ ] Core logic classes with docstrings and type hints
- [ ] ORM models added to `src/db/models.py` (check for name/table collisions)
- [ ] Alembic migration with correct `down_revision` (check chain)
- [ ] Streamlit dashboard in `app/pages/<module>.py` with `st.tabs()`
- [ ] Test file in `tests/test_<module>.py` with class-based organization
- [ ] Documentation in `docs/PRD-XX-<title>.md`
- [ ] All tests passing: `python3 -m pytest tests/test_<module>.py -v`
- [ ] No `metadata` column name conflicts in ORM
- [ ] No `__tablename__` collisions in ORM

### Source files for reference

- `src/db/models.py` -- Central ORM models (218 tables, ~5280 lines)
- `alembic/env.py` -- Migration environment configuration
- `alembic/versions/` -- All 178 migration files
- `app/nav_config.py` -- Navigation configuration (10 sections, 106+ pages)
- `app/styles.py` -- Global CSS theme
- `app/pages/home.py` -- AI Chat home page
