from pymongo import MongoClient

# --- KẾT NỐI MONGODB ---
client = MongoClient("mongodb://localhost:27017/")
db = client["CellphoneS_Project"]
col = db["products_final"]

# --- ĐỊNH NGHĨA DỮ LIỆU CẦN XÓA ---
# Xóa nếu tên sản phẩm chứa thông báo lỗi của Chrome hoặc giá = 0 (do lỗi)
query = {
    "$or": [
        {"product_name": {"$regex": "Your connection is not private"}},
        {"product_name": {"$regex": "Privacy error"}},
        {"product_name": {"$regex": "site can't be reached"}},
        {"price_sale": 0} 
    ]
}

# --- THỰC HIỆN XÓA ---
deleted = col.delete_many(query)

print("---------------------------------------------------")
print(f"✅ ĐÃ XÓA THÀNH CÔNG: {deleted.deleted_count} SẢN PHẨM LỖI.")
