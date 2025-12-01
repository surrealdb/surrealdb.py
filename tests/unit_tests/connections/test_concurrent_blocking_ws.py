"""
Tests for thread-safety of BlockingWsSurrealConnection in concurrent scenarios.

These tests verify that the fix for the race condition works correctly,
ensuring responses are not mixed up when multiple threads share a connection.
"""

import concurrent.futures
from collections.abc import Generator
from typing import Any

import pytest

from surrealdb.connections.blocking_ws import BlockingWsSurrealConnection
from surrealdb.data.types.record_id import RecordID


@pytest.fixture
def setup_data(
    blocking_ws_connection: BlockingWsSurrealConnection,
) -> Generator[None, None, None]:
    """Setup test data before each test and cleanup after."""
    blocking_ws_connection.query("DELETE user;")
    blocking_ws_connection.query("DELETE likes;")
    blocking_ws_connection.query("DELETE document;")
    blocking_ws_connection.query("CREATE user:1 SET name = 'User 1';")
    blocking_ws_connection.query("CREATE user:2 SET name = 'User 2';")
    yield
    blocking_ws_connection.query("DELETE user;")
    blocking_ws_connection.query("DELETE likes;")
    blocking_ws_connection.query("DELETE document;")


def test_concurrent_insert_relation(
    blocking_ws_connection: BlockingWsSurrealConnection, setup_data: None
) -> None:
    """
    Test that concurrent insert_relation calls don't get mixed up responses.

    This test simulates the FastAPI scenario where multiple concurrent requests
    share the same connection. Before the fix, responses could be returned to
    the wrong caller.
    """
    errors = []

    def insert_relation_task(task_id: int):
        """Execute an insert_relation and verify the response."""
        try:
            result = blocking_ws_connection.insert_relation(
                "likes",
                {
                    "in": RecordID("user", str(task_id % 2 + 1)),
                    "out": RecordID("likes", task_id),
                },
            )

            # Verify we got the correct response for this specific request
            expected_out = RecordID("likes", task_id)
            actual_out = result[0]["out"]

            if actual_out != expected_out:
                errors.append(
                    f"Task {task_id}: Expected out={expected_out}, got {actual_out}"
                )

            return result
        except Exception as e:
            errors.append(f"Task {task_id} failed: {e}")
            raise

    # Run 10 concurrent insert_relation operations
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(insert_relation_task, i) for i in range(10)]
        concurrent.futures.wait(futures)

    # Assert no errors occurred
    assert len(errors) == 0, f"Concurrent operations had errors: {errors}"


def test_concurrent_create(
    blocking_ws_connection: BlockingWsSurrealConnection, setup_data: None
) -> None:
    """
    Test that concurrent create calls don't get mixed up responses.
    """
    errors = []

    def create_task(task_id: int):
        """Execute a create and verify the response."""
        try:
            result = blocking_ws_connection.create(
                RecordID("document", task_id), {"content": f"Document {task_id}"}
            )

            # Verify we got the correct response
            expected_id = RecordID("document", task_id)
            actual_id = result["id"]

            if actual_id != expected_id:
                errors.append(
                    f"Task {task_id}: Expected id={expected_id}, got {actual_id}"
                )

            if result["content"] != f"Document {task_id}":
                errors.append(f"Task {task_id}: Got wrong content: {result['content']}")

            return result
        except Exception as e:
            errors.append(f"Task {task_id} failed: {e}")
            raise

    # Run 10 concurrent create operations
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_task, i) for i in range(10)]
        concurrent.futures.wait(futures)

    # Assert no errors occurred
    assert len(errors) == 0, f"Concurrent operations had errors: {errors}"


def test_concurrent_mixed_operations(
    blocking_ws_connection: BlockingWsSurrealConnection, setup_data: None
) -> None:
    """
    Test that mixing different operation types concurrently works correctly.

    This is the most realistic test - it mixes insert_relation and create calls
    just like a real FastAPI application might do.
    """
    errors = []

    def insert_relation_task(task_id: int):
        """Execute an insert_relation."""
        try:
            result = blocking_ws_connection.insert_relation(
                "likes",
                {"in": RecordID("user", "1"), "out": RecordID("likes", task_id)},
            )

            expected_out = RecordID("likes", task_id)
            if result[0]["out"] != expected_out:
                errors.append(
                    f"insert_relation {task_id}: Wrong response {result[0]['out']}"
                )

            return result
        except Exception as e:
            errors.append(f"insert_relation {task_id} failed: {e}")
            raise

    def create_task(task_id: int):
        """Execute a create."""
        try:
            result = blocking_ws_connection.create(
                RecordID("document", task_id), {"content": f"Document {task_id}"}
            )

            expected_id = RecordID("document", task_id)
            if result["id"] != expected_id:
                errors.append(f"create {task_id}: Wrong response {result['id']}")

            return result
        except Exception as e:
            errors.append(f"create {task_id} failed: {e}")
            raise

    # Mix insert_relation and create operations
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(20):
            if i % 2 == 0:
                futures.append(executor.submit(insert_relation_task, i))
            else:
                futures.append(executor.submit(create_task, i))

        concurrent.futures.wait(futures)

    # Assert no errors occurred
    assert len(errors) == 0, f"Concurrent mixed operations had errors: {errors}"


def test_sequential_operations_still_work(
    blocking_ws_connection: BlockingWsSurrealConnection, setup_data: None
) -> None:
    """
    Ensure the thread-safety fix doesn't break normal sequential usage.
    """
    # Sequential operations should work exactly as before

    # Create a document
    doc = blocking_ws_connection.create(RecordID("document", 100), {"content": "Test"})
    assert doc["id"] == RecordID("document", 100)
    assert doc["content"] == "Test"

    # Create a relation
    relation = blocking_ws_connection.insert_relation(
        "likes", {"in": RecordID("user", "1"), "out": RecordID("document", 100)}
    )
    assert relation[0]["in"] == RecordID("user", "1")
    assert relation[0]["out"] == RecordID("document", 100)

    # Query to verify
    result = blocking_ws_connection.query(
        "SELECT * FROM document WHERE id = document:100;"
    )
    assert len(result) == 1
    assert result[0]["content"] == "Test"
