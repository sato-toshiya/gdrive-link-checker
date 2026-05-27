import os
import re
import sys
import requests

# ================= 設定 =================
# 💡 2つのサイトで使い回せるように、環境変数からフォルダ名を受け取れるようにします
DATA_DIR = os.environ.get("WIKI_DATA_DIR", "wiki_data")
WEBHOOK_URL = os.environ.get("GAS_WEBHOOK_URL")
# GASのコード内に書いた合言葉（SECURITY_TOKEN）と同じものをここに書きます
SECURITY_TOKEN = os.environ.get("GAS_SECURITY_TOKEN", "my_dokuwiki_secret_token_1234")
# ========================================

if not WEBHOOK_URL:
    print("❌ エラー: GitHub Secretsに GAS_WEBHOOK_URL が設定されていません。")
    sys.exit(1)

drive_url_pattern = re.compile(r'https://drive\.google\.com/[^\s\]|]+')
links_to_check = []

# URLからGoogleドライブのファイルIDを抽出する関数
def extract_file_id(url):
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if match: return match.group(1)
    match = re.search(r'id=([a-zA-Z0-9-_]+)', url)
    if match: return match.group(1)
    return None

print("🔍 ダウンロードしたWikiデータのスキャンを開始します...")

for root, dirs, files in os.walk(DATA_DIR):
    for file in files:
        if file.endswith(".txt"):
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, DATA_DIR)
            page_name = relative_path.replace(os.sep, ":").replace(".txt", "")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                urls = drive_url_pattern.findall(content)
                for url in set(urls):
                    file_id = extract_file_id(url)
                    if file_id:
                        links_to_check.append({
                            "page": page_name,
                            "id": file_id,
                            "url": url
                        })
            except Exception as e:
                print(f"⚠️ ファイル読み込み失敗: {file_path} ({e})")

if not links_to_check:
    print("✅ Wiki内にGoogleドライブのリンクは見つかりませんでした。")
    sys.exit(0)

print(f"📡 GAS Webhookへデータを送信中... (チェック対象: {len(links_to_check)}件)")

# GASに送るデータのかたまりを作成
payload = {
    "token": SECURITY_TOKEN,
    "links": links_to_check
}

try:
    # GAS WebhookにPOSTリクエストを送信
    response = requests.post(WEBHOOK_URL, json=payload, timeout=300)
    
    if response.status_code != 200:
        print(f"❌ GAS側でエラーが発生しました (Status {response.status_code})")
        sys.exit(1)
        
    result_data = response.json()
    if "error" in result_data:
        print(f"❌ GAS内部エラー: {result_data['error']}")
        sys.exit(1)
        
    broken_links = result_data.get("broken_links", [])
    
    print("\n" + "="*40)
    print("📊 チェック完了！")
    print("="*40)
    
    if broken_links:
        print(f"❌ リンク切れ・エラーが {len(broken_links)} 件見つかりました。\n")
        for link in broken_links:
            print(f"・対象URL  : {link['url']}")
            print(f"  Wikiページ: {link['page']}")
            print(f"  エラー理由: {link['reason']}\n")
        sys.exit(1) # GitHubのアクションをエラーにして通知を飛ばす
    else:
        print("✅ すべてのGoogleドライブリンクは正常にアクセス可能です！")
        sys.exit(0)

except Exception as e:
    print(f"💥 GASとの通信に失敗しました: {e}")
    sys.exit(1)