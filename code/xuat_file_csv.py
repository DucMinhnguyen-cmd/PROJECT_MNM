import pandas as pd
from pymongo import MongoClient

def export_to_csv():
    print("⏳ Đang kết nối MongoDB...")
    client = MongoClient("mongodb://localhost:27017/")
    db = client["CellphoneS_Project"]
    col = db["products_final"]

    # 1. Lấy toàn bộ dữ liệu (Bỏ cột _id nhìn cho đỡ rối)
    data = list(col.find({}, {"_id": 0}))
    
    if len(data) == 0:
        print("❌ Chưa có dữ liệu nào trong Database!")
        return

    print(f"📦 Đã tải {len(data)} dòng dữ liệu.")
    print("⚙️ Đang xử lý và làm sạch dữ liệu...")

    # 2. Chuyển sang DataFrame (Bảng)
    df = pd.DataFrame(data)

    # 3. XỬ LÝ ĐẶC BIỆT: Tách cột 'specs' (Thông số kỹ thuật) ra thành từng cột riêng
    # Nếu không tách, nó sẽ là 1 đống text khó phân tích
    if 'specs' in df.columns:
        # Dùng json_normalize để tách dictionary thành các cột
        specs_df = pd.json_normalize(df['specs'])
        
        # Xóa cột specs cũ và ghép các cột mới vào
        df = df.drop(columns=['specs'])
        df = pd.concat([df, specs_df], axis=1)

    # 4. Sắp xếp lại cột cho đẹp (Tên, Giá, Hãng lên đầu)
    cols = list(df.columns)
    priority = ['product_name', 'price_sale', 'price_original', 'discount_rate', 'category', 'brand']
    # Đưa các cột ưu tiên lên đầu, các cột còn lại (thông số) để phía sau
    new_order = [c for c in priority if c in cols] + [c for c in cols if c not in priority]
    df = df[new_order]

    # 5. Xuất file
    # encoding='utf-8-sig' là BẮT BUỘC để mở Excel không bị lỗi phông chữ Việt
    file_name = "cellphones_data_clean.csv"
    df.to_csv(file_name, index=False, encoding="utf-8-sig")

    print(f"✅ XUẤT THÀNH CÔNG! File nằm tại: {file_name}")
    print(f"📊 Kích thước bảng: {df.shape[0]} dòng x {df.shape[1]} cột")

if __name__ == "__main__":
    export_to_csv()