import asyncio
import os

from app.integrations.wordpress_client import WordPressClient, WordPressError


async def main() -> None:
    pw = os.getenv("WORDPRESS_APP_PASSWORD", "")
    print("pw_len", len(pw.replace(" ", "")))
    client = WordPressClient(
        os.getenv("WORDPRESS_BASE_URL", "https://www.buyersbox.co.jp"),
        os.getenv("WORDPRESS_USERNAME", "corefighter-api"),
        pw,
    )
    try:
        me = await client._request("GET", "/users/me")
        print("AUTH_OK", me.get("name"), me.get("id"))
    except WordPressError as exc:
        print("AUTH_FAIL", str(exc)[:220].replace("\n", " "))


if __name__ == "__main__":
    asyncio.run(main())
