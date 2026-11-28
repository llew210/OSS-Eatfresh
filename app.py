import math
import os
import re
import uuid
from datetime import date, timedelta

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, url_for)

from src import recipes  # 김서현 님 코드: import해도 실행되는 부분이 없어 바로 사용 가능

app = Flask(__name__)
app.secret_key = "dev-key"  # flash 메시지에 필요 (나중에 .env로 이동)
# Flask - secret_key
# -> Flask가 flash 메세지를 브라우저 쿠키에 잠깐 담아 두는데, 이 때 쿠키가 변조되지 않았는지 확인하려고 이 키로 서명함
# flash()를 호출하려면 secret key가 필요함
# 인터넷에 실제로 배포하려면 .env로 옮겨야 하지만 로컬 서버에서 사용할 것이므로 "dev-key" 그대로 둬도 됨.

# ------------------------------------------------------------
# 영수증 업로드 설정
#   사진은 이 컴퓨터의 uploads/ 폴더에만 저장하고, 외부로 보내지 않는다.
#   (uploads/*는 .gitignore에 등록되어 있음)
# ------------------------------------------------------------
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB 초과 업로드는 413 에러
UPLOAD_DIR = os.path.join(app.root_path, "uploads")
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|jpeg|png|webp)$")

CONFIDENCE_THRESHOLD = 0.90  # 이 값 이하로 읽힌 품목은 사용자에게 다시 확인받는다
UNITS = ("g", "개")
# 재료의 보관 방식은 사용자에게 묻지 않는다. (이 프로젝트의 보관 방식 = 레시피로 만든 완성 요리의 냉장/냉동)
# schema.sql의 storage 컬럼이 NOT NULL이라 임시로 기본값만 넣는다. => 컬럼 정리 후 삭제
DEFAULT_STORAGE = "냉장"


# ------------------------------------------------------------
# 더미 데이터 1: DB 행 (db/schema.sql의 컬럼 이름을 그대로 사용)
#   나중에 ingredients.list_all() 결과(src/ingredients.py)로 교체
#   날짜는 "오늘 기준"으로 만들어서, 언제 실행해도 D-day가 의미 있게 나옴
# ------------------------------------------------------------
def _day(n):
    return (date.today() + timedelta(days=n)).isoformat()

# 나중에 SQLite에서 꺼낸 실제 재료 목록 입력 + '_day()'함수 삭제
# 저장된 재료를 전부 꺼내서 app.py가 쓰는 모양으로 돌려주는 함수 추가하기(src/ingredients.py) => SQLite 결과를 튜플로 주면 안되고 dict(row) 형태로 줘야 함
DUMMY_INGREDIENTS = [
    {"id": 1, "name": "파",   "quantity": 1,   "unit": "개", "storage": "냉장", "purchase_date": _day(-3), "expiry_date": _day(1)},
    {"id": 2, "name": "두부", "quantity": 1,   "unit": "개", "storage": "냉장", "purchase_date": _day(-3), "expiry_date": _day(2)},
    {"id": 3, "name": "양파", "quantity": 2,   "unit": "개", "storage": "냉장", "purchase_date": _day(-5), "expiry_date": _day(3)},
    {"id": 4, "name": "배추", "quantity": 300, "unit": "g",  "storage": "냉장", "purchase_date": _day(-2), "expiry_date": _day(7)},
    {"id": 5, "name": "계란", "quantity": 10,  "unit": "개", "storage": "냉장", "purchase_date": _day(-2), "expiry_date": _day(14)},
]

# ------------------------------------------------------------
# 더미 데이터 2: OCR 결과 (src/ocr.py의 rows와 같은 모양, 글자만 남김)
#   "한 줄 = 글자 조각들의 리스트". 영수증 화면을 만들 때 사용
# ------------------------------------------------------------
# 나중에 업로드된 영수증에서 읽은 실제 결과 입력
DUMMY_OCR_ROWS = [
    ["2026-11-18", "14:02"],
    ["두부", "1", "2,500"],
    ["양파", "2", "3,000"],
    ["계란", "10", "5,980"],
]


# ------------------------------------------------------------
# 임시 도우미 함수 (src/expiry.py => 소비기한 남은 일수 계산 함수, 임박 재료 선정 함수, )
# ------------------------------------------------------------
#유통기한까지 남은 일수 계산
def with_d_day(rows):
    """DB 행에 d_day(남은 일수)를 계산해서 붙인다."""
    today = date.today()
    result = []
    for r in rows:
        d_day = (date.fromisoformat(r["expiry_date"]) - today).days
        result.append({**r, "d_day": d_day})
    return result

#임박한 재료 선정 함수
def get_expiring_soon(rows, days=3):
    """남은 기간이 days일 이하인 재료를 임박 순으로 반환."""
    soon = [r for r in with_d_day(rows) if r["d_day"] <= days]
    return sorted(soon, key=lambda r: r["d_day"])

#DB 행을 추천 함수 입력으로 바꾸고, 화면용 충족률과 부족 재료를 붙임 => ??
def build_recommendations(rows):
    """recipes.recommend()는 이름 리스트 2개를 받으므로, DB 행에서 이름만 뽑아서 넘긴다.
    화면에 필요한 충족률/부족 재료는 recipes.py의 함수로 계산해서 붙인다."""
    my_items = [r["name"] for r in rows]
    urgent_items = [r["name"] for r in get_expiring_soon(rows)]

    result = []
    for r in recipes.recommend(urgent_items, my_items):
        missing = [n for n in recipes.get_names(r)
                   if n not in recipes.basic_items and n not in my_items]
        result.append({
            "name": r["name"],
            "match_rate": recipes.have_rate(r, my_items),
            "missing": missing,
        })
    return result


# ------------------------------------------------------------
# 임시 함수 1: 소비기한 추정 (src/expiry.py가 완성되면 그쪽 함수로 교체)
#   ※ 아래 일수는 화면 시연용 '임시 값'이다. 출처가 확인된 값이 아니므로
#      실제 값은 data/reference/expiry_reference.csv(출처 포함)로 대체해야 한다.
#   교체할 때는 함수 이름/인자(name, purchase_date)만 맞추면 된다.
# ------------------------------------------------------------
TEMP_SHELF_DAYS = {   # 일수(냉장 보관 기준으로 가정)
    "두부": 5, "계란": 21, "양파": 30, "파": 7, "대파": 7, "감자": 30,
    "당근": 14, "애호박": 7, "배추": 7, "토마토": 7, "시금치": 3,
    "표고버섯": 5, "팽이버섯": 5, "청양고추": 7,
}
TEMP_DEFAULT_DAYS = 3    # 표에 없는 품목: 불확실하면 짧게(CONTRIBUTING 7장 원칙)


def estimate_expiry_date(name, purchase_date):
    """품목명과 구매일(YYYY-MM-DD)을 받아 예상 소비기한(YYYY-MM-DD)을 돌려준다."""
    days = TEMP_SHELF_DAYS.get(name, TEMP_DEFAULT_DAYS)
    return (date.fromisoformat(purchase_date) + timedelta(days=days)).isoformat()


# ------------------------------------------------------------
# 임시 함수 2: OCR 실행 (src/receipt_ocr.py를 함수로 바꾸면 교체)
#   지금 receipt_ocr.py는 import하면 바로 실행되는 스크립트라 가져다 쓸 수 없다.
#   analyze_receipt(image_path)가 아래와 같은 모양의 dict를 돌려주게 만들면 된다.
#   (receipt_ocr.py의 receipt_data와 같은 키)
# ------------------------------------------------------------
def run_ocr(image_path):
    """임시: 실제 OCR 대신 확인 화면을 시험하기 위한 더미 결과를 돌려준다."""
    return {
        "purchase_date": _day(-1),
        "products": [
            {"product_no": "001", "raw_product_name": "두부", "product_name": "두부",
             "name_candidates": ["두부"], "quantity": 1, "quantity_source": "ocr",
             "name_confidence": 0.97},
            {"product_no": "002", "raw_product_name": "양파", "product_name": "양파",
             "name_candidates": ["양파"], "quantity": 2, "quantity_source": "ocr",
             "name_confidence": 0.93},
            {"product_no": "003", "raw_product_name": "계린", "product_name": "계린",
             "name_candidates": ["계린", "계란"], "quantity": 10, "quantity_source": "calculated",
             "name_confidence": 0.81},
            {"product_no": "004", "raw_product_name": "대마", "product_name": "대마",
             "name_candidates": ["대마", "대파"], "quantity": None, "quantity_source": "unknown",
             "name_confidence": 0.74},
        ],
    }


# ------------------------------------------------------------
# 임시 함수 3: 재료 저장 (src/ingredients.py가 완성되면 SQLite INSERT로 교체)
#   지금은 DUMMY_INGREDIENTS(메모리)에 추가한다. 서버를 다시 켜면 사라진다.
# ------------------------------------------------------------
def save_ingredients(items):
    """items: schema.sql 컬럼과 같은 키를 가진 dict 목록(id 제외)."""
    next_id = max((r["id"] for r in DUMMY_INGREDIENTS), default=0) + 1
    for offset, item in enumerate(items):
        DUMMY_INGREDIENTS.append({"id": next_id + offset, **item})


# ------------------------------------------------------------
# 영수증 화면 도우미
# ------------------------------------------------------------
BLANK_ITEM = {"name": "", "quantity": None, "unit": "개",
              "expiry_date": "", "low_confidence": False, "confirmed": False,
              "confidence_pct": None, "candidates": []}


def ocr_product_to_item(product):
    """OCR 결과 1건(product)을 확인 화면에서 쓰는 모양으로 바꾼다."""
    name = product["product_name"]
    conf = product.get("name_confidence") or 0.0
    return {
        **BLANK_ITEM,
        "name": name,
        "quantity": product["quantity"],
        "low_confidence": conf <= CONFIDENCE_THRESHOLD or not name.strip(),
        "confidence_pct": round(conf * 100),
        "candidates": [c for c in product["name_candidates"] if c != name],
    }


def form_to_item(form_row):
    """저장 요청의 한 줄을 확인 화면에서 쓰는 모양으로 되돌린다(검증 실패로 다시 보여줄 때)."""
    conf = form_row["conf"]
    return {
        **BLANK_ITEM,
        "name": form_row["name"],
        "quantity": form_row["quantity"] or None,
        "unit": form_row["unit"] or "개",
        "expiry_date": form_row["expiry_date"],
        "low_confidence": form_row["low"] == "1",
        "confirmed": form_row["confirmed"] == "1",
        "confidence_pct": int(conf) if conf.isdigit() else None,
    }


def read_form_rows(form):
    """같은 이름으로 여러 번 들어온 입력값을 '한 줄 = dict' 목록으로 묶는다."""
    keys = ["name", "quantity", "unit", "expiry_date", "low", "confirmed", "conf"]
    columns = {k: form.getlist(k) for k in keys}
    rows = []
    for i in range(len(columns["name"])):
        rows.append({k: (columns[k][i].strip() if i < len(columns[k]) else "") for k in keys})
    return rows


def is_iso_date(text):
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def valid_image_name(name):
    """uploads/에 실제로 있는 우리가 만든 파일 이름일 때만 돌려준다."""
    if name and IMAGE_NAME_RE.match(name) and os.path.isfile(os.path.join(UPLOAD_DIR, name)):
        return name
    return None


def render_review(items, purchase_date, image):
    return render_template("receipt_review.html", items=items,
                           purchase_date=purchase_date or "", image=image,
                           blank_item=BLANK_ITEM)


@app.route("/")
def home():
    return render_template(
        "home.html",
        expiring=get_expiring_soon(DUMMY_INGREDIENTS),
        recommended=build_recommendations(DUMMY_INGREDIENTS),
    )


# ------------------------------------------------------------
# 영수증 등록: 1) 사진 선택 -> 2) 인식 결과 확인/수정 -> 3) 저장
# ------------------------------------------------------------
@app.route("/receipt")
def receipt():
    return render_template("receipt_upload.html")


@app.route("/receipt/analyze", methods=["POST"])
def receipt_analyze():
    file = request.files.get("receipt")
    if not file or not file.filename:
        flash("영수증 사진을 선택해 주세요.")
        return redirect(url_for("receipt"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        flash("jpg, png, webp 형식의 사진만 올릴 수 있어요.")
        return redirect(url_for("receipt"))

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = uuid.uuid4().hex + ext
    file.save(os.path.join(UPLOAD_DIR, filename))

    result = run_ocr(os.path.join(UPLOAD_DIR, filename))
    items = [ocr_product_to_item(p) for p in result["products"]]
    if not result["purchase_date"]:
        flash("영수증에서 구매일을 읽지 못했어요. 구매일을 직접 입력해 주세요.")
    return render_review(items, result["purchase_date"], filename)


@app.route("/receipt/manual")
def receipt_manual():
    """영수증 없이 직접 입력(OCR을 쓰지 않는 대안 경로)."""
    return render_review([], date.today().isoformat(), None)


@app.route("/receipt/image/<filename>")
def receipt_image(filename):
    if not IMAGE_NAME_RE.match(filename):
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/receipt/save", methods=["POST"])
def receipt_save():
    purchase_date = request.form.get("purchase_date", "").strip()
    image = valid_image_name(request.form.get("image", ""))
    rows = read_form_rows(request.form)

    errors = []
    if not is_iso_date(purchase_date):
        errors.append("구매일을 입력해 주세요.")

    clean = []
    for n, row in enumerate(rows, start=1):
        if not row["name"] and not row["quantity"]:
            continue  # 비어 있는 줄은 무시
        if not row["name"]:
            errors.append(f"{n}번째 품목의 재료명을 입력해 주세요.")
            continue
        try:
            qty = float(row["quantity"])
            if not math.isfinite(qty) or qty <= 0:
                raise ValueError
        except ValueError:
            errors.append(f"'{row['name']}'의 수량을 0보다 큰 숫자로 입력해 주세요.")
            continue
        if row["unit"] not in UNITS:
            errors.append(f"'{row['name']}'의 단위가 올바르지 않아요.")
            continue
        if row["expiry_date"] and not is_iso_date(row["expiry_date"]):
            errors.append(f"'{row['name']}'의 소비기한 형식이 올바르지 않아요.")
            continue
        if row["low"] == "1" and row["confirmed"] != "1":
            errors.append(f"'{row['name']}'은(는) 인식 신뢰도가 낮아 확인이 필요해요.")
            continue
        clean.append({
            "name": row["name"],
            "quantity": int(qty) if qty == int(qty) else qty,
            "unit": row["unit"],
            "storage": DEFAULT_STORAGE,
            "expiry_date": row["expiry_date"],   # 비어 있으면 아래에서 추정
        })

    if not clean and not errors:
        errors.append("등록할 재료가 없어요. 품목을 하나 이상 입력해 주세요.")

    if errors:
        for message in errors:
            flash(message)
        return render_review([form_to_item(r) for r in rows], purchase_date, image)

    # 소비기한을 입력하지 않은 품목은 추정값으로 채운다
    estimated = 0
    for item in clean:
        if not item["expiry_date"]:
            item["expiry_date"] = estimate_expiry_date(item["name"], purchase_date)
            estimated += 1
        item["purchase_date"] = purchase_date

    save_ingredients(clean)

    # 영수증 사진은 개인정보가 있을 수 있으므로 저장이 끝나면 지운다
    if image:
        try:
            os.remove(os.path.join(UPLOAD_DIR, image))
        except OSError:
            pass

    message = f"재료 {len(clean)}개를 등록했어요."
    if estimated:
        message += f" (소비기한 자동 추정 {estimated}개)"
    flash(message)
    return redirect(url_for("home"))


@app.errorhandler(413)
def too_large(_error):
    flash("사진 용량이 너무 커요. 10MB 이하의 사진을 올려 주세요.")
    return redirect(url_for("receipt"))


# ------------------------------------------------------------
# 아직 만들지 않은 페이지: 메뉴 링크가 깨지지 않도록 임시 화면만 보여 줍니다.
# ------------------------------------------------------------
@app.route("/ingredients")
def ingredient_list():
    return render_template("placeholder.html", title="냉장고")


@app.route("/recipes")
def recipe_list():
    return render_template("placeholder.html", title="추천 레시피")


@app.route("/recipes/<recipe_name>")
def recipe_detail(recipe_name):
    return render_template("placeholder.html", title=recipe_name)


if __name__ == "__main__":
    app.run(debug=True)