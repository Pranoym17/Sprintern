import uuid
from pathlib import Path

from api.models import NotificationChannel
from api.notifications.message_builder import build_test_message


def main() -> None:
    output = Path(__file__).resolve().parents[2] / ".tmp" / "notification-previews"
    output.mkdir(parents=True, exist_ok=True)
    profile_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    email = build_test_message(
        profile_id=profile_id,
        recipient="preview@example.com",
        channel=NotificationChannel.EMAIL,
        nonce="preview",
    )
    telegram = build_test_message(
        profile_id=profile_id,
        recipient="preview-chat",
        channel=NotificationChannel.TELEGRAM,
        nonce="preview",
    )
    (output / "daily-digest.html").write_text(email.html, encoding="utf-8")
    (output / "daily-digest.txt").write_text(email.text, encoding="utf-8")
    (output / "telegram.txt").write_text(telegram.text, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
