from flask import Flask, request, abort, jsonify
import logging
import os
import sqlite3
from dotenv import load_dotenv
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    ImageMessage, StickerMessage, StickerSendMessage
)
from linebot.models import VideoMessage, LocationMessage, LocationSendMessage, VideoSendMessage
# 在文件頂部新增以下導入
from linebot.models import (
    ImageSendMessage, VideoSendMessage, LocationSendMessage
)
import google.generativeai as genai

# 初始化 Flask 和日誌
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger()

# 載入環境變數
load_dotenv()
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# 檢查環境變數
if not all([CHANNEL_SECRET, CHANNEL_TOKEN, GEMINI_KEY]):
    logger.error("❌ 請檢查 .env 檔案中的環境變數是否設定正確")
    exit(1)

# 初始化 LINE 和 Gemini
line_bot_api = LineBotApi(CHANNEL_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
genai.configure(api_key=GEMINI_KEY)
gemini_model = genai.GenerativeModel('models/gemini-1.5-flash')

# 初始化資料庫
def init_db():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                (id INTEGER PRIMARY KEY, user_id TEXT, message TEXT)''')
    conn.commit()
    conn.close()
init_db()

# ====================== 路由設定 ====================== #
@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ====================== 歷史對話 API ====================== #
@app.route("/history/<user_id>", methods=["GET"])
def get_history(user_id):
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute("SELECT * FROM history WHERE user_id = ?", (user_id,))
    data = [{"id": row[0], "message": row[2]} for row in c.fetchall()]
    conn.close()
    return jsonify(data), 200

@app.route("/history/<user_id>", methods=["DELETE"])
def delete_history(user_id):
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"}), 200

# ====================== 訊息處理 ====================== #
def save_message(user_id, message):
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute("INSERT INTO history (user_id, message) VALUES (?, ?)", (user_id, message))
    conn.commit()
    conn.close()

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    user_msg = event.message.text

    save_message(user_id, user_msg)

    # 新增情緒分析邏輯
    if user_msg.lower().startswith("分析情緒:"):
        text_to_analyze = user_msg.replace("分析情緒:", "").strip()
        try:
            # 調用 Gemini 分析情緒
            prompt = f"""
            請分析以下文本的情緒，分為「正面」、「中性」或「負面」。
            並簡短說明原因（限 50 字內）。
            
            文本：{text_to_analyze}
            ---
            情緒分析結果：
            """
            response = gemini_model.generate_content(prompt)
            ai_reply = response.text
        except Exception as e:
            ai_reply = "情緒分析失敗，請稍後再試。"
            logger.error(f"❌ Gemini 錯誤: {str(e)}")

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=ai_reply)
        )
        return

    # 新增邏輯：根據使用者輸入觸發圖片/影片回复
    if user_msg.lower() == "image":
        # 回覆圖片
        image_message = ImageSendMessage(
            original_content_url="https://drive.google.com/uc?export=view&id=1CHpVo2aLucZOhCj68vNFEzMB7r70jgGW",
            preview_image_url="https://drive.google.com/uc?export=view&id=1CHpVo2aLucZOhCj68vNFEzMB7r70jgGW"
        )
        line_bot_api.reply_message(event.reply_token, image_message)
        return  

    elif user_msg.lower() == "video":
        # 回覆影片
        video_message = VideoSendMessage(
            original_content_url="https://drive.google.com/uc?export=download&id=1BlxpTOvWku4Xy8Wh85lxdH9G9cBESMSR",
            preview_image_url="https://drive.google.com/uc?export=view&id=1CQZuufQ7jVxA1MWtc470iedbQ-U1ruMa"
        )
        line_bot_api.reply_message(event.reply_token, video_message)
        return  

    try:
        response = gemini_model.generate_content(user_msg)
        ai_reply = response.text
    except Exception as e:
        ai_reply = "無法生成回覆，請稍後再試。"
        logger.error(f"❌ Gemini 錯誤: {str(e)}")

    save_message("bot", ai_reply)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    # 保存圖片紀錄
    save_message(event.source.user_id, "[圖片消息]")

    # 回覆一張預設圖片
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="很棒的照片喔！")
    )

@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker(event):
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(package_id="11537", sticker_id="52002734")
    )

@handler.add(MessageEvent, message=VideoMessage)
def handle_video(event):
    # 保存影片紀錄
    save_message(event.source.user_id, "[影片消息]")

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="已收到影片！")
    )

@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    # 保存位置消息紀錄
    save_message(event.source.user_id, f"[位置消息] {event.message.address}")

    # 示例：回覆一個固定位置
    line_bot_api.reply_message(
        event.reply_token,
        LocationSendMessage(
            title="國立臺灣大學",
            address="台北市大安區羅斯福路四段1號",
            latitude=25.0173405,
            longitude=121.5397518
        )
    )

# ====================== 主程式 ====================== #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)