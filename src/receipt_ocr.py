import numpy as np
import cv2

import easyocr

from pathlib import Path

project_dir = Path(__file__).resolve().parent.parent

image_path = project_dir / "data" / "raw_receipts" / "KakaoTalk_20261122_141036137_01.jpg"
print("프로젝트 경로:", project_dir)
print("이미지 경로:", image_path)
print("파일 존재 여부:", image_path.is_file())
if not image_path.is_file():
    raise FileNotFoundError("이미지를 찾을 수 없습니다")

else:
    reader = easyocr.Reader(['ko','en'],gpu=False)

    image_data = np.fromfile(str(image_path),dtype=np.uint8)
    image = cv2.imdecode(image_data,cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("이미지를 읽을 수 없습니다.")
    results = reader.readtext(image,detail=1)

    text_data = []

    for bbox, text, confidence in results:
        x = sum(point[0] for point in bbox)/4
        y = sum(point[1] for point in bbox)/4

        text_data.append({
            "text": text,
            "x": x,
            "y": y,
            "confidence": confidence
        })

text_data.sort(key=lambda item: item["y"])

rows = []

y_threshold = 15

for item in text_data:
    matched = False

    for row in rows:
        average_y = sum(
            word["y"] for word in row
        ) / len(row)

        if abs(item["y"] - average_y) <= y_threshold:
            row.append(item)
            matched = True
            break
    if not matched:
        rows.append([item])
for row in rows:
    row.sort(key=lambda item: item["x"])

print("--결과--")

for i, row in enumerate(rows, start=1):
    texts = [item["text"] for item in row]
    print(f"{i}행:{' | '.join(texts)}")

import re
from datetime import datetime

def clean_product_name(text):
    text = text.lstrip("'\"")
    text = re.sub(r"^\d{3}\s*","",text)
    text = re.sub(r"\d{1,3}(?:,\d{3})+[)]?"," ",text)
    text = re.sub(r"(?<!\w)\d{8,}(?!\w)"," ",text)
    text = re.sub(r"\s+"," ",text).strip()

    return text

def extract_product_name(group):
    lines = group["lines"]

    candidates = []

    for line in lines:
        cleaned = clean_product_name(line)

        if not cleaned:
            continue

        if any(word in cleaned for word in["할인","합인","특매"]):
            continue

        if not re.search(r"[가-힣A-Za-z]",cleaned):
            continue

        if re.fullmatch(r"-?\d{1,3},[\dOoCcGg]{3,4}.*",cleaned):
            continue

        if re.fullmatch(r"[\dOdGg]{8,}",cleaned):
            continue

        if re.fullmatch(r"[0-9Oo]+[gG]",cleaned):
            print(f"상품번호{group['product_no']} 규격 후보: {cleaned}")
            continue

        candidates.append(cleaned)

    if not candidates:
        return "", []

    print(f"상품번호{group['product_no']} 상품명 후보: {candidates}")

    return candidates[0], candidates

def get_name_confidence(group):
    lines = group["lines"]
    ocr_rows = group["ocr_rows"]

    for i,line in enumerate(lines):
        text = line.lstrip("'\"")
        text = re.sub(r"^\d{3}\s*","",text).strip()

        if not text:
            continue

        if(
            "할인" in text
            or "합인" in text
            or "특매" in text
        ):
            continue

        if re.fullmatch(r"[\d,\s#]+",text):
            continue

        name_items = []

        for item in ocr_rows[i]:
            item_text = item["text"].strip()

            if re.fullmatch(r"\d{3}",item_text):
                continue

            if re.fullmatch(r"[\d,\s#]+",item_text):
                continue

            name_items.append(item)
        if name_items:
            confidence_values = [
                float(item["confidence"])
                for item in name_items
            ]

            return sum(confidence_values) / len(confidence_values)

    return 0.0

purchase_date = None

for row in rows:
    line = " ".join(item["text"] for item in row)

    match = re.search(
        r"판매일\s*:\s*(\d{2}-\d{2}-\d{2})",
        line
    )

    if match:
        data_text = match.group(1)

        try:
            purchase_date = datetime.strptime(
                data_text, "%y-%m-%d"
            ).strftime("%Y-%m-%d")
        except ValueError:
            purchase_date = None

        break

print("\n--구매날짜")
print(purchase_date) 

products = []

print("\n--상품 정보 추출")

product_groups = []
current_group = None
in_product_section = False

for row in rows:
    texts = [item["text"] for item in row]
    line = " ".join(texts).strip()
    line = line.lstrip("'\"")

    if "상품명" in line:
        in_product_section = True
        continue

    if not in_product_section:
        continue

    if (
        "합인금액" in line.replace(" ","")
        or "합인급액" in line.replace(" ","")
        or "면세물품" in line
        or "면세물들" in line
        or ("합" in line and "계" in line)
    ):
        break

    line = re.sub(r"^00[gG](?=\D|$)", "009", line)

    match = re.match(r"^(00[1-9]|0[1-9]\d|[1-9]\d{2})(?=\D|$)",line)

    if match:
        if current_group is not None:
            product_groups.append(current_group)

        current_group = {
            "product_no": match.group(1),
            "lines": [line],
            "ocr_rows": [list(row)]
        }
    elif current_group is not None:
        current_group["lines"].append(line)
        current_group["ocr_rows"].append(list(row))

if current_group is not None:
    product_groups.append(current_group)

print("\n--상품 정보 자동 추출")

products = []

for group in product_groups:
    lines = group["lines"]

    ocr_confidence = get_name_confidence(group)

    raw_product_name = re.sub(
        r"^\d{3}\s*",
        "",
        lines[0]
    ).strip()

    if not raw_product_name and len(lines) > 1:
        raw_product_name = lines[1].strip()

    product_name, name_candidates = extract_product_name(group)

    price_candidates = []

    for line in lines[1:]:
        if(
            "할인" in line
            or "합인" in line
            or "특매" in line
            or re.search(r"-\s*\d",line)
        ):
            continue

        numbers = re.findall(
            r"\d{1,3}(?:,\d{3})+",
            line
        )

        for number in numbers:
            price_candidates.append(
                int(number.replace(",",""))
            )
    if len(price_candidates) >= 2:
        unit_price = price_candidates[0]
        total_price = price_candidates[-1]

    else:
        unit_price = None
        total_price = None

    quantity = None
    quantity_source = "unknown"

    for line in lines[1:]:
        tokens = line.split()

        for token in tokens:
            cleaned = token.strip()

            if cleaned.isdigit() and len(cleaned) <= 2:
                candidate = int(cleaned)

                if(
                    candidate > 0
                    and unit_price is not None
                    and total_price is not None
                    and unit_price * candidate == total_price
                ):
                    quantity = candidate
                    quantity_source = "ocr"
                    break

        if quantity_source == "ocr":
            break

    if quantity is None and unit_price and total_price:
        if total_price % unit_price == 0:
             quantity = total_price // unit_price
             quantity_source = "calculated"

    needs_review = bool(
        ocr_confidence < 0.90
        or quantity is None
        or not product_name.strip()
        or len(name_candidates) > 1
    )    

    product = {
        "product_no": group["product_no"],
        "raw_product_name": raw_product_name,
        "product_name": product_name,
        "name_candidates": name_candidates,
        "quantity": quantity,
        "quantity_source": quantity_source,
        "name_confidence": round(float(ocr_confidence),4),
        "needs_review": needs_review
    }

    products.append(product)

receipt_data = {
    "purchase_date": purchase_date,
    "products": products
}

print("\n--EatFresh 영수증 분석 결과")
print("구매날짜:",receipt_data["purchase_date"])

for product in receipt_data["products"]:
    print(product)

print("\n--사용자 확인 필요 상품")

review_products = [
    product
    for product in products
    if product["needs_review"]
]

if review_products:
    for product in review_products:
        print(
            f"상품번호: {product['product_no']}, "
            f"상품명: {product['product_name']}, "
            f"수량: {product['quantity']}, "
            f"상품명 신뢰도: {product['name_confidence']:.2%}"     
        )
        if len(product["name_candidates"]) > 1:
            print(" -> 여러 상품명 후보 발견")
            print(f" -> 후보 목록: {product['name_candidates']}")

else:
    print("사용자 확인이 필요한 상품이 없습니다.")
# target_row = rows[12]

# center_y = sum(
#     item["y"] for item in target_row
# ) / len(target_row)

# height, width = image.shape[:2]

# y1 = max(0, int(center_y - 40))
# y2 = min(height, int(center_y + 40))

# cropped = image[y1:y2, :]

# enlarged = cv2.resize(
#     cropped,
#     None,
#     fx=3,
#     fy=3,
#     interpolation=cv2.INTER_CUBIC
# )

# enlarged_results = reader.readtext(
#     enlarged,
#     detail=1
# )

# print("\n--확대 결과")

# for bbox, text, confidence in enlarged_results:
#     print(
#         f"글자:{text},"
#         f"신뢰도:{confidence:.2f}"
#     )