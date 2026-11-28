import math
import os
import re
import uuid
from datetime import date, timedelta

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, url_for)

from src import recipes

app = Flask(__name__)
app.secret_key = "dev-key"
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
# 저장된 소비기한이 없기 때문

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
    soon = [r for r in with_d_day(rows) if r["d_day"] <= days]
    return sorted(soon, key=lambda r: r["d_day"])

#DB 행을 추천 함수 입력으로 바꾸고, 화면용 충족률과 부족 재료를 붙임
#recipes.py에 '부족한 재료 이름 목록'을 돌려주는 함수가 없어 app.py에서 직접 레시피와 재료를 불러와 비교하여 부족 재료 목록 만듦.
#부족한 재료 목록을 recipes.py에서 함수로 만들어 app.py에서는 호출만 하는 것이 안전할 수 있음
def build_recommendations(rows):
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


@app.route("/")
def home():
    return render_template(
        "home.html",
        expiring=get_expiring_soon(DUMMY_INGREDIENTS),
        recommended=build_recommendations(DUMMY_INGREDIENTS),
    )


# ------------------------------------------------------------
# 아직 만들지 않은 페이지: 메뉴 링크가 깨지지 않도록 임시 화면만 보여 줍니다.
# ------------------------------------------------------------
@app.route("/ingredients")
def ingredient_list():
    return render_template("placeholder.html", title="냉장고")


@app.route("/receipt")
def receipt():
    return render_template("placeholder.html", title="영수증 등록")


@app.route("/recipes")
def recipe_list():
    return render_template("placeholder.html", title="추천 레시피")


@app.route("/recipes/<recipe_name>")
def recipe_detail(recipe_name):
    return render_template("placeholder.html", title=recipe_name)


if __name__ == "__main__":
    app.run(debug=True)