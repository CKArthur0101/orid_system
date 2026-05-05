"""
把繪本 PDF（圖片型）的文字用 GPT-4o-mini Vision 抽出來，
然後把 story_excerpts 寫回 book_pack_week1.json。

執行方式：
  cd local-shared-data
  $env:OPENAI_API_KEY="sk-..."    # 設定你的 API Key
  python ocr_book_pdf.py

執行一次就好，結果會直接存到 book_pack_week1.json。
"""

import base64
import json
import os
import sys
import time

import fitz  # pip install pymupdf
from openai import OpenAI

PDF_PATH = r"C:\Users\User\Downloads\阿松爺爺的柿子樹.pdf"
BOOK_PACK_PATH = "book_pack_week1.json"

# 第 1~2 頁通常是封面/版權頁，直接跳過
SKIP_PAGES = {0, 1, 31, 32}  # 0-indexed: 封面、版頁、最後版權

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def page_to_base64(page, zoom: float = 2.0) -> str:
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    return base64.b64encode(pix.tobytes("png")).decode()


def ocr_page(page_num: int, b64_img: str) -> str:
    """Send one page image to GPT-4o-mini and get the text back."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "這是台灣出版的中文繪本《阿松爺爺的柿子樹》的其中一頁。"
                            "書裡的主要角色有：阿松爺爺（想獨占柿子的老爺爺）、哎喲奶奶（新搬來的鄰居）、小朋友們。"
                            "書裡的水果是「柿子」（不是橘子、柑子）。"
                            "請**逐字**把頁面上出現的所有文字完整抽出來，保持原本的順序，**不要改字、不要猜測、不要補充**。"
                            "只輸出書上的文字本身，不要加任何說明或標記。"
                            "如果這頁沒有文字（只有圖），請只輸出「（無文字）」。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_img}"},
                    },
                ],
            }
        ],
        max_tokens=500,
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def main():
    if "OPENAI_API_KEY" not in os.environ:
        print("錯誤：請先設定 OPENAI_API_KEY 環境變數。")
        sys.exit(1)

    doc = fitz.open(PDF_PATH)
    total = len(doc)
    print(f"共 {total} 頁，開始 OCR…")

    pages_text: dict[int, str] = {}

    for i in range(total):
        if i in SKIP_PAGES:
            print(f"  Page {i+1:02d}: 跳過")
            continue

        b64 = page_to_base64(doc[i])
        print(f"  Page {i+1:02d}: 送出 OCR…", end="", flush=True)
        try:
            text = ocr_page(i + 1, b64)
            pages_text[i + 1] = text
            preview = text[:60].replace("\n", "↵")
            print(f" ✓  {preview}")
        except Exception as e:
            print(f" ✗  {e}")
            pages_text[i + 1] = ""

        time.sleep(0.5)  # 避免 rate limit

    # 整理結果：過濾掉「無文字」頁，轉成 story_excerpts list
    story_excerpts = []
    for page_num in sorted(pages_text):
        text = pages_text[page_num].strip()
        if text and "（無文字）" not in text:
            story_excerpts.append({"page": page_num, "text": text})

    print(f"\n共 {len(story_excerpts)} 頁有文字。")

    # 寫回 book_pack
    with open(BOOK_PACK_PATH, encoding="utf-8") as f:
        book_pack = json.load(f)

    book_pack["story_excerpts"] = story_excerpts

    with open(BOOK_PACK_PATH, "w", encoding="utf-8") as f:
        json.dump(book_pack, f, ensure_ascii=False, indent=2)

    print(f"已更新 {BOOK_PACK_PATH}！")
    print("\n前 3 頁範例：")
    for ex in story_excerpts[:3]:
        print(f"  [P{ex['page']}] {ex['text'][:100]}")


if __name__ == "__main__":
    main()
