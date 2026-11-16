import easyocr

from pathlib import Path

project_dir = Path(__file__).resolve().parent.parent

image_path = project_dir / "data" / "sample_receipts" / "KakaoTalk_20261115_223640739.jpg"

if not image_path.is_file():
    print("이미지를 찾을 수 없습니다")

else:
    reader = easyocr.Reader(['ko','en'],gpu=False)

    results = reader.readtext(str(image_path),detail=1)

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

import cv2

image = cv2.imread(str(image_path))

if image is None:
    print("이미지를 읽을 수 없습니다")

else:
    target_row = rows[12]

    center_y = sum(
        item["y"] for item in target_row
    )/len(target_row)

height, width = image.shape[:2]

y1 = max(0, int(center_y - 40))
y2 = min(height, int(center_y + 40))

cropped = image[y1:y2, :]

enlarged = cv2.resize(
    cropped,
    None,
    fx=3,
    fy=3,
    interpolation=cv2.INTER_CUBIC
)

enlarged_results = reader.readtext(
    enlarged,
    detail=1
)

print("\n--확대 결과")

for bbox, text, confidence in enlarged_results:
    print(
        f"글자:{text},"
        f"신뢰도:{confidence:.2f}"
    )
