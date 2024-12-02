import asyncio

from surrealdb import AsyncSurrealDB


async def main():
    async with AsyncSurrealDB(url="ws://localhost:8000") as db:
        # Sign up a new user
        token = await db.sign_up(username="new_user", password="secure_password")
        print(f"New User Token: {token}")

        # Sign in as an existing user
        token = await db.sign_in(username="existing_user", password="secure_password")
        print(f"Signed In Token: {token}")

        # Authenticate using a token
        await db.authenticate(token=token)
        print("Authentication successful!")


if __name__ == '__main__':
    asyncio.run(main())
