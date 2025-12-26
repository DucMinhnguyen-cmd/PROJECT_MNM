import sqlite3
import time
import json
import re
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager

# =========================================================
# 1. CẤU HÌNH DATABASE (15 CỘT + RATING)
# =========================================================
base_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(base_dir, "cellphones_final_complete.db")
TARGET_COUNT = 2200 

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_url TEXT UNIQUE,
    sku TEXT,
    brand TEXT,
    product_name TEXT,
    category TEXT,
    type TEXT,
    price_sale INTEGER,
    price_original INTEGER,
    discount_rate TEXT,
    five_star_count INTEGER,       -- Số lượng đánh giá
    spec_ram TEXT,
    spec_storage TEXT,
    spec_screen TEXT,
    spec_chip TEXT,
    img_url TEXT,
    scraped_date DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()

# =========================================================
# 2. CÁC HÀM XỬ LÝ (QUAN TRỌNG)
# =========================================================
def clean_number(text):
    """Lấy số từ chuỗi"""
    if not text: return 0
    clean = re.sub(r"[^\d]", "", str(text))
    return int(clean) if clean else 0

def detect_brand(name):
    name = name.lower()
    brands = {'iphone': 'Apple', 'ipad': 'Apple', 'macbook': 'Apple', 'samsung': 'Samsung', 
              'xiaomi': 'Xiaomi', 'oppo': 'OPPO', 'vivo': 'Vivo', 'asus': 'ASUS', 
              'dell': 'Dell', 'hp': 'HP', 'lenovo': 'Lenovo', 'acer': 'Acer', 
              'msi': 'MSI', 'sony': 'Sony', 'huawei': 'Huawei', 'garmin': 'Garmin'}
    for k, v in brands.items():
        if k in name: return v
    return "Khác"

def get_specs(driver):
    specs = {"ram": "", "storage": "", "screen": "", "chip": ""}
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, ".technical-content li, .technical-content tr, .box-kithuat li")
        for row in rows:
            txt = row.text.lower()
            val = row.text.split(":")[-1].strip()
            if "ram" in txt and not specs["ram"]: specs["ram"] = val
            elif any(x in txt for x in ["bộ nhớ trong", "ổ cứng", "dung lượng"]) and "pin" not in txt and not specs["storage"]:
                specs["storage"] = val
            elif "kích thước màn hình" in txt and not specs["screen"]: specs["screen"] = val
            elif any(x in txt for x in ["chipset", "cpu", "vi xử lý"]) and not specs["chip"]: specs["chip"] = val
    except: pass
    return specs

# --- ĐÂY LÀ HÀM BẠN BỊ THIẾU Ở BƯỚC TRƯỚC ---
def get_json_data(driver):
    """Lấy Giá, Ảnh, SKU và Rating từ dữ liệu ẩn (JSON-LD)"""
    info = {"price": 0, "img": "", "sku": ""}
    try:
        scripts = driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
        for script in scripts:
            try:
                content = script.get_attribute("innerHTML")
                data = json.loads(content)
                if isinstance(data, list): data = data[0]
                
                # 1. Lấy giá & SKU
                if "offers" in data:
                    offers = data["offers"]
                    if isinstance(offers, list): offers = offers[0]
                    if "price" in offers: info["price"] = clean_number(offers["price"])
                    if "lowPrice" in offers: info["price"] = clean_number(offers["lowPrice"])
                    if "sku" in offers: info["sku"] = offers["sku"]
                
                # 2. Lấy Ảnh
                if "image" in data:
                    img = data["image"]
                    info["img"] = img[0] if isinstance(img, list) else img
                # Ưu tiên tìm thấy giá > 0
                if info["price"] > 0: break
            except: continue
    except: pass
    return info

# =========================================================
# 3. CHẠY CRAWL
# =========================================================
options = Options()
options.add_argument("--headless") # Chạy ẩn cho nhanh
service = Service(GeckoDriverManager().install())
driver = webdriver.Firefox(service=service, options=options)

targets = [
    {"url": "https://cellphones.com.vn/mobile.html", "cat": "Smartphone", "type": "Mới"},
    {"url": "https://cellphones.com.vn/laptop.html", "cat": "Laptop", "type": "Mới"},
    {"url": "https://cellphones.com.vn/tablet.html", "cat": "Tablet", "type": "Mới"},
    {"url": "https://cellphones.com.vn/hang-cu/dien-thoai.html", "cat": "Smartphone", "type": "Cũ"},
    {"url": "https://cellphones.com.vn/hang-cu/laptop.html", "cat": "Laptop", "type": "Cũ"},
    {"url": "https://cellphones.com.vn/hang-cu/may-tinh-bang.html", "cat": "Tablet", "type": "Cũ"},
    {"url": "https://cellphones.com.vn/dong-ho-thong-minh.html", "cat": "Smartwatch", "type": "Mới"},
    {"url": "https://cellphones.com.vn/thiet-bi-am-thanh/tai-nghe.html", "cat": "Tai nghe", "type": "Phụ kiện"},
]

total_saved = 0

try:
    for target in targets:
        if total_saved >= TARGET_COUNT: break
        print(f"\n🚀 ĐANG XỬ LÝ: {target['cat']} ({target['type']})")
        driver.get(target['url'])
        time.sleep(3)

        # 1. LOAD MORE
        print("   -> Đang tải danh sách link...")
        for _ in range(50):
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                btn = WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-show-more")))
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)
            except: break
        
        # 2. LẤY LINK
        links = []
        elems = driver.find_elements(By.CSS_SELECTOR, ".product-info-container a, .product-item a, .item-product a")
        for e in elems:
            try:
                l = e.get_attribute("href")
                if l and "http" in l and "cellphones.com.vn" in l: links.append(l)
            except: continue
        links = list(set(links))
        print(f"   -> ✅ Tìm thấy {len(links)} link. Bắt đầu Deep Crawl...")

        # 3. VÀO TỪNG LINK
        for link in links:
            if total_saved >= TARGET_COUNT: break
            
            cursor.execute("SELECT 1 FROM products WHERE product_url=?", (link,))
            if cursor.fetchone(): continue 

            try:
                driver.get(link)
                
                # Tên sản phẩm
                try: name = driver.find_element(By.TAG_NAME, "h1").text.strip()
                except: continue
                
                # --- GỌI HÀM LẤY DỮ LIỆU ---
                json_info = get_json_data(driver) # Đã có hàm này rồi
                
                price_sale = json_info["price"]
                img_url = json_info["img"]
                sku = json_info["sku"]
                rating_count = json_info["rating"]

                # Fallback Rating
                five_star_count = 0

                try:
                    # 1. Cuộn chuột xuống sâu để kích hoạt nạp (Lazy Load) phần Review
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 2000);")
                    time.sleep(2) # Chờ 2 giây để thanh Progress kịp hiện ra

                    # 2. Tìm khối chứa các thanh sao
                    # Selector này bao quát và chính xác hơn trên Cellphones
                    rating_block = driver.find_element(By.CSS_SELECTOR, "div.boxReview-score__list")

                    # 3. Tìm tất cả các thẻ progress (thường sắp xếp từ 5 sao xuống 1 sao)
                    progress_bars = rating_block.find_elements(By.TAG_NAME, "progress")

                    if len(progress_bars) > 0:
                        # progress đầu tiên [0] tương ứng với 5 sao
                        # Lấy giá trị từ thuộc tính 'value' (đây chính là con số lượng đánh giá)
                        val = progress_bars[0].get_attribute("value")
                        five_star_count = int(val) if val else 0

                except Exception as e:
                    # In ra lỗi nếu cần debug, nếu không thì cứ để mặc định là 0
                    # print(f"Lỗi lấy 5 sao: {e}")
                    five_star_count = 0

                # Fallback Giá
                if price_sale == 0:
                    try:
                        txt = driver.find_element(By.CSS_SELECTOR, ".product__price--show").text
                        price_sale = clean_number(txt)
                    except: pass

                # Lọc giá rác
                if price_sale < 500000 and target['type'] == "Mới" and "phụ kiện" not in target['cat'].lower():
                    price_sale = 0

                # Giá gốc
                price_orig = price_sale
                try:
                    txt = driver.find_element(By.CSS_SELECTOR, ".product__price--through").text
                    tmp = clean_number(txt)
                    if tmp > price_sale: price_orig = tmp
                except: pass
                
                discount = "0%"
                if price_orig > price_sale and price_sale > 0:
                    val = int(((price_orig - price_sale) / price_orig) * 100)
                    discount = f"-{val}%"

                specs = get_specs(driver)

                # Lưu DB
                cursor.execute("""
                    INSERT INTO products (
                        product_url, sku, brand, product_name, category, type, 
                        price_sale, price_original, discount_rate, five_star_count,
                        spec_ram, spec_storage, spec_screen, spec_chip, img_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    link, sku, detect_brand(name), name, target['cat'], target['type'],
                    price_sale, price_orig, discount,five_star_count,
                    specs['ram'], specs['storage'], specs['screen'], specs['chip'], img_url
                ))
                conn.commit()
                total_saved += 1
                
                print(f"✅ [{total_saved}] {name[:20]}... | {price_sale:,}đ | ⭐{five_star_count}")

            except Exception: continue

except KeyboardInterrupt:
    print("\n🛑 Dừng thủ công.")

finally:
    driver.quit()
    conn.close()
    
    # Xuất Excel
    try:
        print("\n🔄 Đang xuất ra Excel...")
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM products", conn)
        df_clean = df[df['price_sale'] > 0]
        df_clean.to_excel("Ket_Qua_Cellphones_Final.xlsx", index=False)
        print(f"🎉 THÀNH CÔNG! File Excel: Ket_Qua_Cellphones_Final.xlsx")
        print(f"📊 Tổng số dòng: {len(df_clean)}")
    except: pass