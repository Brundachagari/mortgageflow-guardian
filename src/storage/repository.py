"""Where processed document records live.

Phase 1 uses an in-memory store so everything runs on your laptop with no AWS.
It sits behind an abstract interface, so in Phase 2 a DynamoDB-backed version can
drop in without changing any pipeline code -- the same "depend on the interface"
trick used for the AI provider.

Access patterns are intentionally simple -- get by id, look up by hash, list by
status -- which is exactly why a key-value store (DynamoDB) fits better than a
relational database here: no joins, just fast key lookups.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class DocumentRepository(ABC):
    @abstractmethod
    def get(self, document_id: str) -> Optional[dict]: ...

    @abstractmethod
    def find_by_hash(self, document_hash: str) -> Optional[dict]: ...

    @abstractmethod
    def save(self, record: dict) -> None: ...

    @abstractmethod
    def list_by_status(self, status: str) -> list[dict]: ...


class InMemoryRepository(DocumentRepository):
    """A dictionary pretending to be a database. Perfect for tests and demos."""

    def __init__(self) -> None:
        self._by_id: dict[str, dict] = {}

    def get(self, document_id: str) -> Optional[dict]:
        return self._by_id.get(document_id)

    def find_by_hash(self, document_hash: str) -> Optional[dict]:
        # This is the duplicate-detection lookup: has this exact content been
        # processed before? In DynamoDB this becomes a query on a hash index.
        for record in self._by_id.values():
            if record.get("documentHash") == document_hash:
                return record
        return None

    def save(self, record: dict) -> None:
        self._by_id[record["documentId"]] = record

    def list_by_status(self, status: str) -> list[dict]:
        return [r for r in self._by_id.values() if r.get("processingStatus") == status]

    def all(self) -> list[dict]:
        return list(self._by_id.values())


class DynamoDbRepository(DocumentRepository):
    """The real store, used when the code runs as an AWS Lambda.

    It implements the SAME interface as InMemoryRepository, which is exactly why
    the pipeline never had to change: swapping the backend is invisible to the
    business logic. The two indexes referenced here are created in Terraform
    (dynamodb.tf): one on documentHash (duplicate detection) and one on
    processingStatus (listing documents that need review).
    """

    def __init__(self, table_name: str | None = None, region: str | None = None):
        import boto3  # imported lazily so local runs never require boto3

        import os

        table = table_name or os.environ["DOCUMENTS_TABLE"]
        self._table = boto3.resource(
            "dynamodb", region_name=region or os.environ.get("AWS_REGION")
        ).Table(table)

    @staticmethod
    def _to_dynamo(item: dict) -> dict:
        # DynamoDB rejects Python floats; it wants Decimal. Round-tripping
        # through JSON with parse_float=Decimal converts every number safely.
        import decimal
        import json

        return json.loads(json.dumps(item), parse_float=decimal.Decimal)

    @staticmethod
    def _from_dynamo(item: dict | None) -> dict | None:
        # Convert Decimals back to plain int/float for clean JSON output.
        if item is None:
            return None
        import decimal
        import json

        def _default(value):
            if isinstance(value, decimal.Decimal):
                return int(value) if value % 1 == 0 else float(value)
            raise TypeError

        return json.loads(json.dumps(item, default=_default))

    def get(self, document_id: str) -> Optional[dict]:
        resp = self._table.get_item(Key={"documentId": document_id})
        return self._from_dynamo(resp.get("Item"))

    def find_by_hash(self, document_hash: str) -> Optional[dict]:
        from boto3.dynamodb.conditions import Key

        resp = self._table.query(
            IndexName="documentHash-index",
            KeyConditionExpression=Key("documentHash").eq(document_hash),
            Limit=1,
        )
        items = resp.get("Items", [])
        return self._from_dynamo(items[0]) if items else None

    def save(self, record: dict) -> None:
        self._table.put_item(Item=self._to_dynamo(record))

    def list_by_status(self, status: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        resp = self._table.query(
            IndexName="processingStatus-index",
            KeyConditionExpression=Key("processingStatus").eq(status),
        )
        return [self._from_dynamo(i) for i in resp.get("Items", [])]
