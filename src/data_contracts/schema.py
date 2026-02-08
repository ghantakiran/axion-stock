"""Schema definition, versioning, and compatibility checking for data contracts."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .config import CompatibilityMode, ContractStatus, FieldType


@dataclass
class FieldDefinition:
    """Definition of a single field in a data contract schema."""
    name: str
    field_type: FieldType
    required: bool = True
    constraints: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    default: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize field definition to dict."""
        return {
            "name": self.name,
            "field_type": self.field_type.value,
            "required": self.required,
            "constraints": self.constraints,
            "description": self.description,
            "default": self.default,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FieldDefinition":
        """Deserialize field definition from dict."""
        return cls(
            name=data["name"],
            field_type=FieldType(data["field_type"]),
            required=data.get("required", True),
            constraints=data.get("constraints", {}),
            description=data.get("description", ""),
            default=data.get("default"),
        )


@dataclass
class SchemaVersion:
    """A versioned schema containing field definitions."""
    version: str
    fields: List[FieldDefinition] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    changelog: str = ""

    def get_field(self, name: str) -> Optional[FieldDefinition]:
        """Get field definition by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def field_names(self) -> List[str]:
        """Return list of field names."""
        return [f.name for f in self.fields]

    def required_fields(self) -> List[FieldDefinition]:
        """Return list of required fields."""
        return [f for f in self.fields if f.required]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize schema version to dict."""
        return {
            "version": self.version,
            "fields": [f.to_dict() for f in self.fields],
            "created_at": self.created_at.isoformat(),
            "changelog": self.changelog,
        }


@dataclass
class DataContract:
    """A data contract between producer and consumer."""
    contract_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    producer: str = ""
    consumer: str = ""
    schema_version: Optional[SchemaVersion] = None
    status: ContractStatus = ContractStatus.DRAFT
    sla: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""
    tags: List[str] = field(default_factory=list)
    version_history: List[SchemaVersion] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize contract to dict."""
        return {
            "contract_id": self.contract_id,
            "name": self.name,
            "producer": self.producer,
            "consumer": self.consumer,
            "schema_version": self.schema_version.to_dict() if self.schema_version else None,
            "status": self.status.value,
            "sla": self.sla,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "description": self.description,
            "tags": self.tags,
        }


class SchemaBuilder:
    """Builder for constructing schema versions with fluent API."""

    def __init__(self):
        self._fields: List[FieldDefinition] = []
        self._version: str = "1.0.0"
        self._changelog: str = ""

    def set_version(self, version: str) -> "SchemaBuilder":
        """Set the schema version."""
        self._version = version
        return self

    def set_changelog(self, changelog: str) -> "SchemaBuilder":
        """Set the changelog for this version."""
        self._changelog = changelog
        return self

    def add_field(
        self,
        name: str,
        field_type: FieldType,
        required: bool = True,
        constraints: Optional[Dict[str, Any]] = None,
        description: str = "",
        default: Any = None,
    ) -> "SchemaBuilder":
        """Add a field definition to the schema."""
        self._fields.append(
            FieldDefinition(
                name=name,
                field_type=field_type,
                required=required,
                constraints=constraints or {},
                description=description,
                default=default,
            )
        )
        return self

    def build(self) -> SchemaVersion:
        """Build and return the schema version."""
        return SchemaVersion(
            version=self._version,
            fields=list(self._fields),
            changelog=self._changelog,
        )

    @staticmethod
    def from_sample(data: Dict[str, Any], version: str = "1.0.0") -> SchemaVersion:
        """Infer a schema from a sample data record.

        Maps Python types to FieldType:
        - str -> STRING
        - int -> INTEGER
        - float -> FLOAT
        - bool -> BOOLEAN (checked before int)
        - datetime -> DATETIME
        - list -> LIST
        - dict -> MAP
        """
        fields = []
        type_map = {
            str: FieldType.STRING,
            int: FieldType.INTEGER,
            float: FieldType.FLOAT,
            bool: FieldType.BOOLEAN,
            datetime: FieldType.DATETIME,
            list: FieldType.LIST,
            dict: FieldType.MAP,
        }

        for key, value in data.items():
            # Check bool before int since bool is subclass of int
            if isinstance(value, bool):
                ft = FieldType.BOOLEAN
            elif type(value) in type_map:
                ft = type_map[type(value)]
            else:
                ft = FieldType.STRING

            fields.append(
                FieldDefinition(
                    name=key,
                    field_type=ft,
                    required=True,
                )
            )

        return SchemaVersion(version=version, fields=fields)

    @staticmethod
    def diff(v1: SchemaVersion, v2: SchemaVersion) -> List[Dict[str, Any]]:
        """Compute differences between two schema versions.

        Returns a list of change records, each with:
        - change: 'added', 'removed', or 'modified'
        - field: field name
        - details: additional info about the change
        """
        changes = []
        v1_names = {f.name: f for f in v1.fields}
        v2_names = {f.name: f for f in v2.fields}

        # Fields removed in v2
        for name in v1_names:
            if name not in v2_names:
                changes.append({
                    "change": "removed",
                    "field": name,
                    "details": f"Field '{name}' was removed",
                })

        # Fields added in v2
        for name in v2_names:
            if name not in v1_names:
                changes.append({
                    "change": "added",
                    "field": name,
                    "details": f"Field '{name}' was added",
                    "required": v2_names[name].required,
                })

        # Fields modified
        for name in v1_names:
            if name in v2_names:
                f1 = v1_names[name]
                f2 = v2_names[name]
                modifications = []

                if f1.field_type != f2.field_type:
                    modifications.append(
                        f"type changed from {f1.field_type.value} to {f2.field_type.value}"
                    )
                if f1.required != f2.required:
                    modifications.append(
                        f"required changed from {f1.required} to {f2.required}"
                    )
                if f1.constraints != f2.constraints:
                    modifications.append("constraints changed")

                if modifications:
                    changes.append({
                        "change": "modified",
                        "field": name,
                        "details": "; ".join(modifications),
                    })

        return changes

    @staticmethod
    def check_compatibility(
        old: SchemaVersion,
        new: SchemaVersion,
        mode: CompatibilityMode,
    ) -> Tuple[bool, List[str]]:
        """Check compatibility between schema versions.

        Compatibility rules:
        - BACKWARD: New schema can read data written with old schema.
          - No required fields added (optional ok)
          - No field type changes
          - Field removals ok (consumer ignores extra)
        - FORWARD: Old schema can read data written with new schema.
          - No fields removed
          - No field type changes
          - Optional field additions ok
        - FULL: Both backward and forward compatible.
        - NONE: No compatibility checks.
        """
        if mode == CompatibilityMode.NONE:
            return True, []

        issues = []
        old_fields = {f.name: f for f in old.fields}
        new_fields = {f.name: f for f in new.fields}

        if mode in (CompatibilityMode.BACKWARD, CompatibilityMode.FULL):
            # New required fields break backward compat
            for name, f in new_fields.items():
                if name not in old_fields and f.required:
                    issues.append(
                        f"Backward incompatible: new required field '{name}' added"
                    )

            # Type changes break backward compat
            for name in old_fields:
                if name in new_fields:
                    if old_fields[name].field_type != new_fields[name].field_type:
                        issues.append(
                            f"Backward incompatible: field '{name}' type changed "
                            f"from {old_fields[name].field_type.value} to "
                            f"{new_fields[name].field_type.value}"
                        )

        if mode in (CompatibilityMode.FORWARD, CompatibilityMode.FULL):
            # Removed fields break forward compat
            for name in old_fields:
                if name not in new_fields:
                    issues.append(
                        f"Forward incompatible: field '{name}' was removed"
                    )

            # Type changes break forward compat
            for name in old_fields:
                if name in new_fields:
                    if old_fields[name].field_type != new_fields[name].field_type:
                        msg = (
                            f"Forward incompatible: field '{name}' type changed "
                            f"from {old_fields[name].field_type.value} to "
                            f"{new_fields[name].field_type.value}"
                        )
                        if msg not in [i for i in issues]:
                            issues.append(msg)

        compatible = len(issues) == 0
        return compatible, issues
