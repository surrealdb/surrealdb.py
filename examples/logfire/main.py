"""
Logfire + SurrealDB Example

This example demonstrates automatic observability for SurrealDB operations
using Pydantic Logfire. Every database operation is automatically traced,
providing visibility into your database interactions.

Run this example to see how Logfire captures:
- Connection and authentication operations
- CRUD operations (create, select, update, delete)
- Query operations with SurrealQL
- Timing information for each operation
- Automatic scrubbing of sensitive data

All traces are displayed in the console, and can optionally be sent to
the Logfire cloud platform for more advanced analysis.
"""

import asyncio
from typing import Any

from database import get_database, setup_logfire


async def demonstrate_crud_operations(db: Any) -> None:
    """Demonstrate CRUD operations with automatic tracing.
    
    Each operation below creates a span in the trace with:
    - Operation name (e.g., "surrealdb create")
    - Parameters (non-sensitive)
    - Timing information
    - Success/failure status
    
    Args:
        db: SurrealDB connection instance
    """
    print("\n" + "="*60)
    print("CRUD OPERATIONS - Each creates a traced span")
    print("="*60 + "\n")
    
    # CREATE: Create new user records
    # Span: "surrealdb create"
    print("➕ Creating users...")
    user1 = await db.create(
        "user",
        {
            "name": "Alice Smith",
            "email": "alice@example.com",
            "age": 28,
            "role": "admin"
        }
    )
    print(f"   Created user: {user1['id']}")
    
    user2 = await db.create(
        "user",
        {
            "name": "Bob Johnson",
            "email": "bob@example.com",
            "age": 35,
            "role": "user"
        }
    )
    print(f"   Created user: {user2['id']}")
    
    user3 = await db.create(
        "user",
        {
            "name": "Charlie Davis",
            "email": "charlie@example.com",
            "age": 42,
            "role": "user"
        }
    )
    print(f"   Created user: {user3['id']}\n")
    
    # SELECT: Read all users
    # Span: "surrealdb select"
    print("📖 Selecting all users...")
    all_users = await db.select("user")
    print(f"   Found {len(all_users)} users\n")
    
    # QUERY: Use SurrealQL for more complex queries
    # Span: "surrealdb query"
    print("🔍 Querying users with SurrealQL...")
    query_result = await db.query(
        "SELECT * FROM user WHERE age > $min_age ORDER BY age",
        {"min_age": 30}
    )
    print(f"   Found {len(query_result)} users over 30 years old\n")
    
    # UPDATE: Update a user record
    # Span: "surrealdb update"
    print("✏️  Updating user...")
    updated_user = await db.update(
        user1["id"],
        {
            "name": "Alice Smith",
            "email": "alice.smith@example.com",  # Updated email
            "age": 29,  # Updated age
            "role": "admin"
        }
    )
    print(f"   Updated user: {updated_user['id']}\n")
    
    # MERGE: Partially update a user (only specified fields)
    # Span: "surrealdb merge"
    print("🔄 Merging user data...")
    merged_user = await db.merge(
        user2["id"],
        {"role": "moderator"}  # Only update the role field
    )
    print(f"   Merged user: {merged_user['id']}\n")
    
    # DELETE: Delete a user record
    # Span: "surrealdb delete"
    print("🗑️  Deleting user...")
    deleted = await db.delete(user3["id"])
    print(f"   Deleted user: {deleted['id']}\n")


async def demonstrate_authentication(db: Any) -> None:
    """Demonstrate authentication operations with tracing.
    
    Note: These operations were already traced during setup,
    but this shows they can be called explicitly.
    
    Args:
        db: SurrealDB connection instance
    """
    print("\n" + "="*60)
    print("AUTHENTICATION - Already traced during connection")
    print("="*60 + "\n")
    
    print("✅ Authentication operations traced:")
    print("   - signin: Authenticates with username/password")
    print("   - use: Selects namespace and database")
    print("   - Token parameter automatically scrubbed from logs\n")


async def demonstrate_batch_operations(db: Any) -> None:
    """Demonstrate batch operations with tracing.
    
    Args:
        db: SurrealDB connection instance
    """
    print("\n" + "="*60)
    print("BATCH OPERATIONS")
    print("="*60 + "\n")
    
    # INSERT: Insert multiple records at once
    # Span: "surrealdb insert"
    print("📦 Inserting multiple users...")
    batch_users = await db.insert(
        "user",
        [
            {"name": "Diana Prince", "email": "diana@example.com", "age": 30},
            {"name": "Ethan Hunt", "email": "ethan@example.com", "age": 38},
            {"name": "Fiona Gallagher", "email": "fiona@example.com", "age": 26},
        ]
    )
    print(f"   Inserted {len(batch_users)} users\n")
    
    # Query to count all users
    # Span: "surrealdb query"
    print("🔢 Counting all users...")
    count_result = await db.query("SELECT count() FROM user GROUP ALL")
    total = count_result[0]["count"]
    print(f"   Total users in database: {total}\n")


async def cleanup_database(db: Any) -> None:
    """Clean up all test data.
    
    Args:
        db: SurrealDB connection instance
    """
    print("\n" + "="*60)
    print("CLEANUP")
    print("="*60 + "\n")
    
    print("🧹 Cleaning up test data...")
    
    # Delete all users
    # Span: "surrealdb delete"
    await db.delete("user")
    print("   ✅ Deleted all test users\n")


async def main() -> None:
    """Main entry point for the example."""
    print("\n" + "="*60)
    print("LOGFIRE + SURREALDB OBSERVABILITY EXAMPLE")
    print("="*60 + "\n")
    
    # Step 1: Setup Logfire instrumentation
    setup_logfire()
    
    # Step 2: Connect to database
    # Note: Connection operations are also traced!
    db = await get_database()
    
    print("Logfire is now tracing all SurrealDB operations!")
    print("Each operation below creates a span with details about the database call.")
    print("Check your console for timing information and span details.\n")
    
    try:
        # Step 3: Demonstrate authentication tracing
        await demonstrate_authentication(db)
        
        # Step 4: Demonstrate CRUD operations
        await demonstrate_crud_operations(db)
        
        # Step 5: Demonstrate batch operations
        await demonstrate_batch_operations(db)
        
        # Step 6: Clean up
        await cleanup_database(db)
        
    finally:
        # Always close the connection
        await db.close()
    
    print("="*60)
    print("✨ Example complete!")
    print("="*60 + "\n")
    
    print("What happened:")
    print("• Every database operation created a trace span")
    print("• Sensitive data (passwords, tokens) were automatically scrubbed")
    print("• Timing information was captured for each operation")
    print("• All spans are visible in your console output above")
    
    if not hasattr(db, "_logfire_token"):
        print("\n💡 Tip: Set LOGFIRE_TOKEN in .env to send traces to Logfire cloud")
        print("   for advanced dashboards, alerting, and team collaboration.\n")


if __name__ == "__main__":
    asyncio.run(main())
