"""Translate user-facing English error strings in app/ to Japanese."""
from pathlib import Path

REPLACEMENTS = {
    "Incorrect email or password": "メールアドレスまたはパスワードが正しくありません",
    "Inactive user": "このアカウントは無効です",
    "Invalid refresh token": "リフレッシュトークンが無効です",
    "Could not validate credentials": "認証に失敗しました。再ログインしてください",
    "Insufficient permissions for this action": "この操作を行う権限がありません",
    "You do not have access to this store's resources": "この店舗のデータにアクセスする権限がありません",
    "Purchase not found": "買取データが見つかりません",
    "Article not found": "記事が見つかりません",
    "Persona not found": "AIペルソナが見つかりません",
    "User not found": "ユーザーが見つかりません",
    "Store not found": "店舗が見つかりません",
    "Job not found": "ジョブが見つかりません",
    "Rule not found": "ルールが見つかりません",
    "Media not found": "メディアが見つかりません",
    "WordPress site not found": "WordPress接続設定が見つかりません",
    "Email already registered": "このメールアドレスは既に登録されています",
    "You cannot delete the account you are signed in with": "ログイン中のアカウントは削除できません",
    "Article has no version to edit": "編集できる記事バージョンがありません",
    "Invalid media key": "不正なメディアキーです",
    "Only failed/cancelled jobs can be retried": "失敗またはキャンセルされたジョブのみ再試行できます",
    "Job already finished": "このジョブは既に完了しています",
    "Article is not awaiting approval": "この記事は承認待ちではありません",
    "Invalid decision": "不正な承認操作です",
    "Article must be approved and have a WordPress draft": "公開するには記事が承認済みで、WordPress下書きが必要です",
    "No WordPress draft exists yet": "WordPress下書きがまだありません。先に下書き作成を実行してください",
    "Article has no content": "記事本文がありません",
    "Latest similarity check did not pass; regenerate or override required": (
        "類似率チェックに不合格です。本文を再生成するか、類似警告を解除してから公開してください"
    ),
    "No WordPress site configured for this store": "この店舗にWordPress接続が設定されていません",
    "Article is not published to WordPress yet (no related posts available)": (
        "この記事はまだWordPressに公開されていないため、関連記事を取得できません"
    ),
    "Purchase not found for image analysis": "画像解析対象の買取データが見つかりません",
    "No images to analyze": "解析する画像がありません",
    "No active WordPress site configured for this store": "この店舗に有効なWordPress接続がありません",
    "No purchase image found — featured image is required for EXPERIENCE listing": (
        "買取画像がありません。EXPERIENCE掲載にはアイキャッチ画像が必須です"
    ),
    "WordPress media upload returned no source_url": (
        "WordPressへの画像アップロードに失敗しました（URLが返りませんでした）"
    ),
    "Article has no current version": "記事に現行バージョンがありません",
    "Current version missing": "記事バージョンが見つかりません",
    "No WordPress post to update": "更新対象のWordPress投稿がありません",
    "No WordPress draft to publish": "公開するWordPress下書きがありません",
}

# f-string / dynamic fragments
DYNAMIC = [
    (
        'detail=f"Unknown persona(s): {\', \'.join(str(m) for m in missing)}"',
        'detail=f"不明なAIペルソナです: {\', \'.join(str(m) for m in missing)}"',
    ),
    (
        'detail=f"Cannot create WordPress draft from status {article.status.value}"',
        'detail=f"現在の状態（{article.status.value}）からはWordPress下書きを作成できません"',
    ),
    (
        'detail=f"Article cannot be submitted from status {article.status.value}"',
        'detail=f"現在の状態（{article.status.value}）からは承認申請できません"',
    ),
    (
        'f"Featured image upload failed ({main.storage_key}): {exc}. "\n'
        '            "MinIO must be running and the image key must exist."',
        'f"アイキャッチ画像のアップロードに失敗しました（{main.storage_key}）: {exc}。"\n'
        '            "MinIOが起動していること、画像キーが存在することを確認してください。"',
    ),
]


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    changed = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        orig = text
        for en, ja in REPLACEMENTS.items():
            text = text.replace(en, ja)
        for en, ja in DYNAMIC:
            text = text.replace(en, ja)
        if text != orig:
            path.write_text(text, encoding="utf-8")
            changed.append(path.relative_to(root.parent))
    print(f"updated {len(changed)} files")
    for c in changed:
        print(c)


if __name__ == "__main__":
    main()
