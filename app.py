from datetime import date, timedelta

from flask import Flask, render_template

from src import recipes  # 김서현 님 코드: import해도 실행되는 부분이 없어 바로 사용 가능

app = Flask(__name__)
app.secret_key = "dev-key"  # flash 메시지에 필요 (나중에 .env로 이동)
# Flask - secret_key
# -> Flask가 flash 메세지를 브라우저 쿠키에 잠깐 담아 두는데, 이 때 쿠키가 변조되지 않았는지 확인하려고 이 키로 서명함
# flash()를 호출하려면 secret key가 필요함
# 인터넷에 실제로 배포하려면 .env로 옮겨야 하지만 로컬 서버에서 사용할 것이므로 "dev-key" 그대로 둬도 됨.


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