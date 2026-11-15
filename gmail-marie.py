import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import argparse

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main():
    parser = argparse.ArgumentParser(description="Gmailのメッセージを操作する")
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "-d",
        "--delete",
        action="store_true",
        help="ゴミ箱に移動する（デフォルト）",
    )
    parser.add_argument(
        "-a", "--archive", action="store_true", help="アーカイブする"
    )
    parser.add_argument(
        "-r", "--read", action="store_true", help="既読にする"
    )
    parser.add_argument(
        "-u", "--unread", action="store_true", help="未読にする"
    )
    parser.add_argument(
        "pattern",
        metavar="PATTERN",
        help="Gmail API準拠の検索パターン（例: from:someone@example.com）",
        nargs="?",
    )
    args = parser.parse_args()

    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("./token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # may the cred be with you!!
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        # many services gone to cloud-api but google workspacers are not :-(
        service = build("gmail", "v1", credentials=creds)

        pattern = args.pattern

        if pattern is None:
            query = (
                "from:月刊表現者"  # the most annoying but sometimes useful mails (LoL)
            )
        elif ":" not in pattern:
            query = "from:" + pattern  # if not specified, search by from header.
        else:
            query = pattern
        print(f"'{query}' に一致するメールを検索中...")

        messages = []
        request = service.users().messages().list(userId="me", q=query)

        # retrieve all by pagenation
        while request is not None:
            response = request.execute()
            if "messages" in response:
                messages.extend(response["messages"])
            request = (
                service.users()
                .messages()
                .list_next(previous_request=request, previous_response=response)
            )

        for i, msg in enumerate(messages[:15]):
            payload = (
                service.users()
                .messages()
                .get(
                    id=msg["id"],
                    userId="me",
                    format="metadata",
                    metadataHeaders=["Date", "Subject"],
                )
                .execute()["payload"]["headers"]
            )

            subject = date = "?"
            for data in payload:
                if data["name"] == "Subject":
                    subject = data["value"]
                else:
                    date = data["value"]

            print(f"{i:02d}: {date} {subject}")

        total_count = len(messages)
        if total_count == 0:
            print("対象のメールは見つかりませんでした。")
            return

        if args.archive:
            action_name = "アーカイブ"
            add_label_ids = []
            remove_label_ids = ["INBOX"]
        elif args.read:
            action_name = "既読に"
            add_label_ids = []
            remove_label_ids = ["UNREAD"]
        elif args.unread:
            action_name = "未読に"
            add_label_ids = ["UNREAD"]
            remove_label_ids = []
        else:
            action_name = "ゴミ箱に移動"
            add_label_ids = ["TRASH"]
            remove_label_ids = ["INBOX", "UNREAD"]

        print(f"合計 {total_count} 件のメールが見つかりました。{action_name}します...")
        while True:
            if (ans := input("OK(y/n)？")) == "y":
                break
            elif ans == "n":
                return
            print(ans)

        # for batch execution
        # batchDelete in gmail is delete mails "COMPLETELY".
        # so to move mails safely,  instead of using that label them to TRASH.
        batch_size = 1000
        for i in range(0, total_count, batch_size):
            chunk = messages[i : i + batch_size]
            msg_ids = [msg["id"] for msg in chunk]

            body = {"ids": msg_ids}
            if add_label_ids:
                body["addLabelIds"] = add_label_ids
            if remove_label_ids:
                body["removeLabelIds"] = remove_label_ids

            service.users().messages().batchModify(userId="me", body=body).execute()
            print(f"{i + len(chunk)} / {total_count} 件処理完了...")

        print(f"すべての対象メールを{action_name}しました！")

    except HttpError as error:
        print(f"エラーが発生しました: {error}")


if __name__ == "__main__":
    main()
