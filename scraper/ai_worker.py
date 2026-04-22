import os
import time
import asyncio
import json
import logging
from typing import List, Dict, Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from dotenv import load_dotenv

from google import genai
from google.genai import types

import config

# ==============================================================================
# 1. CẤU HÌNH HỆ THỐNG
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("Thiếu biến môi trường GEMINI_API_KEY. Vui lòng thêm vào file .env")
    exit(1)

# Khởi tạo client theo SDK google-genai mới
ai_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-3.1-flash-lite-preview"

# Cấu hình BATCH_SIZE: Bắt buộc gom đủ 10 items mới gọi API để tiết kiệm quota 500 RPD
BATCH_SIZE = 5

AI_ITEM_TIMEOUT_MINUTES = 3*60  # Đặt số phút muốn bỏ qua tại đây (ví dụ: 60 phút)

# ==============================================================================
# 2. XỬ LÝ LÔ DỮ LIỆU (BATCH PROCESSING)
# ==============================================================================
async def process_batch(collection):
    """
    Xử lý mẻ BATCH_SIZE items.
    Yêu cầu AI đánh giá nên mua hay không. Nếu không mua, vẫn phải cập nhật trạng thái.
    """
    now_ms = int(time.time() * 1000)
    timeout_ms = AI_ITEM_TIMEOUT_MINUTES * 60 * 1000
    cutoff_time = now_ms - timeout_ms

    try:
        # Bước 1: Dọn rác (Timeout Pruning)
        # Các item chờ AI quá thời gian quy định sẽ bị skip thẳng để tránh lãng phí quota API
        prune_result = await collection.update_many(
            {
                "$or": [{"ai_evaluated": False}, {"ai_evaluated": {"$exists": False}}],
                "list_time": {"$lt": cutoff_time}
            },
            {"$set": {"ai_evaluated": True, "evaluated": {"type": 2, "note": "skipped_timeout"}}}
        )
        if prune_result.modified_count > 0:
            logger.info(f"Đã bỏ qua {prune_result.modified_count} items quá hạn (cũ hơn {AI_ITEM_TIMEOUT_MINUTES} phút).")

        # Bước 2: Bốc BATCH_SIZE items (ưu tiên cũ nhất trước trong giới hạn thời gian cho phép)
        cursor = collection.find({
            "$or": [{"ai_evaluated": False}, {"ai_evaluated": {"$exists": False}}],
            "list_time": {"$gte": cutoff_time}
        }).sort("list_time", 1).limit(BATCH_SIZE)
        
        items = await cursor.to_list(length=BATCH_SIZE)
        
        if not items:
            return 0  # Hàng đợi trống

        # =====================================================================
        # CHIẾN THUẬT GOM MẺ (BATCHING) TRÁNH CẠN QUOTA RPD (500 lượt/ngày)
        # =====================================================================
        # Tính tuổi thọ của item cũ nhất trong mẻ (item ở vị trí đầu tiên của list)
        # oldest_age = now_ms - items[0].get("list_time", now_ms)
        
        # Nếu item đã già bằng 80% thời gian cho phép (ví dụ set 60 phút thì 80% là 48 phút)
        # is_approaching_timeout = oldest_age > (timeout_ms * 0.8) 

        # --- CHÚ THÍCH ---
        # Nếu chưa đủ BATCH_SIZE, nhưng item cũ nhất sắp hết hạn 
        # (is_approaching_timeout = True), ta VẪN GỬI.
        # Nếu chưa đủ BATCH_SIZE và cũng chưa hết hạn, ta RETURN để chờ vòng lặp sau gom thêm.
        #if len(items) < BATCH_SIZE and not is_approaching_timeout:
        if len(items) < BATCH_SIZE:
            # Chưa gom đủ số lượng và item cũ nhất vẫn chưa quá mức cảnh báo -> Bỏ qua, chờ thêm
            return 0

        logger.info(f"Gửi {len(items)} items lên Gemini AI ({MODEL_ID}) để thẩm định...")

        # Bước 3: Rút gọn dữ liệu gửi đi (Giảm token)
        payload = []
        for item in items:
            payload.append({
                "_id": item["_id"],
                "subject": item.get("subject", ""),
                "body": item.get("body", ""),
                "price": item.get("price", 0),
                "params": item.get("params", [])
            })

        # Bước 4: Chèn Prompt Tối Ưu Mới Nhất
                # Bước 4: Chèn Prompt Tối Ưu Mới Nhất
        prompt = f"""
**ROLE:** Bạn là chuyên gia định giá đồ cũ (Flipping Expert) tại thị trường Việt Nam năm 2026. Nhiệm vụ duy nhất của bạn là đọc danh sách tin đăng Chợ Tốt và suy nghĩ và chấm điểm THANH KHOẢN, DÒNG TIỀN (khả năng bán lại nhanh trong 3-7 ngày).  và BIÊN LỢI NHUẬN (mua rẻ bán đắt, chênh lệch ít nhất 300k).

**KHUNG THAM CHIẾU THỊ TRƯỜNG ĐỒ CŨ VIỆT NAM 2026:**
Ghi nhớ sâu các nhóm hàng sau trước khi đánh giá:

[NHÓM A - THANH KHOẢN CỰC CAO, BAY TRONG 1-3 NGÀY]
- Điện thoại phổ thông dưới 2 triệu: Samsung A-series cũ, Xiaomi Redmi, iPhone SE/11/12 cũ nhưng thanh khoản tốt, điện thoại đó phải tốt.
- Linh kiện máy tính: RAM, SSD, VGA cũ, CPU đời cũ còn dùng được
- Đồ gia dụng nhỏ HOT: Nồi chiên không dầu, máy xay sinh tố, ấm đun siêu tốc, bếp từ mini
- Thiết bị âm thanh: Loa Bluetooth, tai nghe có dây/không dây (dưới 500k)
- Thể thao & Sức khỏe: Vợt cầu lông, Dụng cụ tập gym đơn lẻ (tạ, dây nhảy), giày thể thao, mỹ phẩm mới, phụ nữ mua nhiều, ...

[NHÓM B - THANH KHOẢN KHÁ, BAY TRONG 3-7 NGÀY]  
- Máy tính bảng iPad cũ (iPad mini, Air đời cũ dưới 3 triệu)
- Laptop học sinh/văn phòng cũ dưới 5 triệu (Core i5/i7 đời 7-10)
- Đồ gia dụng vừa: Lò vi sóng, bàn ủi hơi nước, máy hút bụi mini
- Xe đạp thể thao và xe đạp điện mini
- Dụng cụ cầm tay: Máy khoan, máy cưa mini, bộ tuốc nơ vít


[NHÓM ĐEN - TỪ CHỐI TUYỆT ĐỐI, KHÔNG MUA DÙ GIÁ NÀO]
- Quần áo/giày dép kén size (trừ thương hiệu lớn như Nike/Adidas còn bảo hành)
- Đồ trang trí nội thất, cây cảnh
- Sách giáo khoa, giáo trình cũ
- Thiết bị âm nhạc chuyên dụng (guitar điện, trống, keyboard)
- Điện thoại đời quá cũ (trước 2018), laptop đời quá cũ (Core i3 đời 4-5)
- Giường, nệm, tủ quần áo, sofa, bàn ghế gỗ to (cồng kềnh, tốn xe ba gác)
- Tủ lạnh lớn, máy giặt, máy lạnh (nặng, khó ship, tốn công lắp đặt)
- Bất kỳ thứ gì có chữ: "bán xác", "lỗi nhẹ", "sọc màn hình", "hư main", "dính iCloud", "bypass", "MDM", "hỏng hóc", "chữa cháy", "thay màn" (tôi muốn zin 100%)
- Hàng giả, hàng nhái rõ ràng
- Tin từ cửa hàng/thợ (văn phong quảng cáo, nhiều icon, "bảo hành shop", chụp ảnh trưng bày)
- Điện thoại mẫu cũ < 2018 (cục gạch, ...)
- Giá rao bán bằng hoặc cao hơn giá THU MUA CỦA THỢ đối với đồ cũ cùng tình trạng. 
- Lợi nhuận mỏng: Tiềm năng chênh lệch giá (mua vào - bán ra) dưới 300.000 VNĐ. Không bõ công đi lại và dọn dẹp máy.
- Hàng rác / Lỗi chức năng nặng:** Có chữ "bán xác", "lỗi nhẹ", "sọc màn", "hư main", "mất FaceID", "dính iCloud", "hỏng hóc", "chữa cháy".
- Cửa hàng / Thợ thuyền:** Lời văn sặc mùi con buôn, chụp ảnh tại cửa hàng, có bảo hành shop, nhiều icon lòe loẹt.


**QUY TẮC ĐÁNH GIÁ GIÁ (BẮT BUỘC):**
- So sánh GIÁ RAO BÁN với GIÁ ĐỒ CŨ CÙNG LOẠI trên thị trường (KHÔNG so với giá mới).
- Giá phải thấp hơn tối thiểu 25% so với mặt bằng đồ cũ tương tự mới được xét TYPE 1.
- Nếu giá = 0 hoặc không có giá → TYPE 2 ngay.
- Nhìn tin đăng có icon, quá chuyên nghiệp, quá hiểu về sản phẩm thì có thể là thợ hoặc cửa hàng, nên bỏ quả.

**YÊU CẦU OUTPUT BẮT BUỘC:**
- Đánh giá TOÀN BỘ _id có trong danh sách. Tuyệt đối không bỏ sót bất kỳ _id nào.
- CHỈ trả về 1 mảng JSON hợp lệ. KHÔNG có text nào ngoài JSON.
- Các item TYPE 2 chỉ cần ghi _id và type, không cần giải thích.
- Luôn suy nghĩ về THANH KHOẢN x3.14, DÒNG TIỀN để quyết định nên mua sản phẩm đó hay không. 
- Sử dụng Google Search để tìm kiếm thông tin về sản phẩm, thị trường, giá cả, ... ví dụ "Thông tin sản phẩm + facebook" xem các bài đăng đó nhiều tương tác, mọi người muốn mua sản phẩm đó nhiều không, thanh khoản thế nào.
- Sản phẩm cũ đó phải rẻ hơn so với mặt bằng trung bình chính nó tại thị trường đồ cũ. Khi tôi mua vào, và bán ra thì giá bán ra đó vẫn phải thấp hơn so với giá thị trường thì mới hấp dẫn và thanh khoản cao, nhưng biên độ lợi nhuận vẫn đảm bảo.

Định dạng JSON bắt buộc:
[
  {{
    "_id": <giữ nguyên _id gốc>,
    "type": 1,
    "note": "<Lý do cụ thể tại sao sản phẩm này nên mua, thanh khoản, biên lợi nhuận thế nào.>"
  }},
  {{
    "_id": <giữ nguyên _id gốc>,
    "type": 2,
    "note": "<Lý do tại sao không chọn>"
  }}
]

Danh sách món hàng cần đánh giá:
{json.dumps(payload, ensure_ascii=False)}
"""

        # Bước 5: Gọi AI với chế độ JSON Mode bằng SDK mới (google-genai)
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        # grounding_tool = types.Tool(
        #     google_search=types.GoogleSearch()
        # )

        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(
                thinking_level="HIGH",
                # grounding_config=types.GroundingConfig(
                #     tools=[grounding_tool]
                # )
            ),
            temperature=0.9,
            #tools=[grounding_tool]
        )
        
        # Chạy trong thread để không block asyncio loop
        def call_ai():
            return ai_client.models.generate_content(
                model=MODEL_ID,
                contents=contents,
                config=generate_content_config,
            )
            
        response = await asyncio.to_thread(call_ai)
        
        # Bước 6: Parse và Update Database an toàn
        try:
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            results = json.loads(clean_text)
        except json.JSONDecodeError:
            logger.error("Lỗi Parse JSON từ AI. Nội dung trả về:")
            logger.debug(response.text)
            return 0

        bulk_ops = []
        result_map = {res.get("_id"): res for res in results if res.get("_id")}

        for original_item in payload:
            item_id = original_item["_id"]
            ai_res = result_map.get(item_id, {"type": 2, "note": "Lỗi không được ai xử lý"})
            eval_type = ai_res.get("type", 2)
            note = ai_res.get("note", "")
            update_data = {
                "ai_evaluated": True,
                "evaluated": {
                    "type": eval_type,
                    "note": note
                }
            }

            bulk_ops.append(
                UpdateOne(
                    {"_id": item_id},
                    {"$set": update_data}
                )
            )

        if bulk_ops:
            update_result = await collection.bulk_write(bulk_ops)
            good_deals = sum(1 for res in results if res.get("type") == 1)
            logger.info(f"Đã xử lý {update_result.modified_count} items. Tìm thấy {good_deals} kèo thơm (type 1)!")
            return update_result.modified_count
        return 0

    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
            logger.warning("Google Rate Limit (429) hoặc Hết Quota! Tạm ngủ 60 giây...")
            await asyncio.sleep(60)
        else:
            logger.error(f"Lỗi không xác định khi gọi AI: {e}")
            await asyncio.sleep(15)
        return 0


# ==============================================================================
# 3. HÀM MAIN & VÒNG LẶP
# ==============================================================================
async def run_ai_worker(collection, broadcast_func=None): 
    logger.info("Khởi động Siêu AI Worker Săn Kèo Thơm (chạy ngầm)...")
    
    # Vòng lặp vĩnh cửu
    while True:
        processed_count = await process_batch(collection)
        if processed_count and processed_count > 0 and broadcast_func:
            try:
                await broadcast_func({"type": "AI_EVALUATION_DONE", "count": processed_count})
            except Exception as e:
                logger.error(f"Lỗi broadcast kết quả AI: {e}")
                
        # Nghỉ 5s để đảm bảo không bao giờ vượt 15 req/phút (RPM)
        # Kể cả có xử lý liên tục cũng chỉ tối đa 12 req/phút
        await asyncio.sleep(15)