basic_items = ["소금","간장","설탕","후추","참기름"]

recipes = [
    {"name": "된장찌개", "ingredients": ["두부","양파","파","애호박","감자","청양고추","된장","고춧가루","다진마늘","멸치"]},
    {"name": "두부전", "ingredients": ["두부","파","계란","부침가루","당근"]},
    {"name": "두부전골", "ingredients": ["두부","양파","파","배추","표고버섯","팽이버섯","당근","청양고추","다진마늘","고춧가루","멸치"]},
    {"name": "토마토 계란볶음", "ingredients": ["토마토","계란","파","케첩"]},
    {"name": "감자조림", "ingredients": ["감자","양파","당근","청양고추","다진마늘","올리고당"]},
    {"name": "시금치무침", "ingredients": ["시금치","파","다진마늘","참기름","깨"]},
    {"name": "참치마요덮밥", "ingredients": ["밥","참치캔","양파","마요네즈","김","깨"]},
]

def count_urgent(recipe,urgent_item):
    count = 0
    for item in recipe["ingredients"]:
        if item in urgent_item:
            count += 1
    return count

def have_rate(recipe, my_items):
    count = 0
    total = 0
    for item in recipe["ingredients"]:
        if item not in basic_items:
            total += 1
            if item in my_items:
                count += 1
    return count / total

def recommend(urgent_items, my_items):
    result = sorted(
        recipes,
        key=lambda r: (count_urgent(r, urgent_items), have_rate(r, my_items)),
        reverse=True
    )
    return result[:3]

def make_result_text(urgent_items, my_items):
    texts = []
    rank = 1
    for r in recommend(urgent_items, my_items):
        texts.append(str(rank) + "순위:" + r["name"])
        rank += 1
    return texts

#테스트용
if __name__ == "__main__":
    urgent_items = ["두부","양파","파"]
    my_items = ["배추","양파","계란"]
    for text in make_result_text(urgent_items, my_items):
        print(text)
