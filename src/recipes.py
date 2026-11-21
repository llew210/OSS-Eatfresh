from cooking import recipes

basic_items = ["소금","간장","설탕","후추","참기름"]

def get_names(recipe):
    names = []
    for item in recipe["ingredients"]:
        names.append(item["name"])
    return names


def count_urgent(recipe,urgent_item):
    count = 0
    for name in get_names(recipe):
        if name in urgent_item:
            count += 1
    return count

def have_rate(recipe, my_items):
    count = 0
    total = 0
    for name in get_names(recipe):
        if name not in basic_items:
            total += 1
            if name in my_items:
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
        rate = round(have_rate(r, my_items) * 100)
        texts.append(str(rank) + "순위:" + r["name"] + " (보유율 " + str(rate) + "%)")
        rank += 1
    return texts

def get_recipe_detail(name):
    for r in recipes:
        if r["name"] == name:
            return r
    return None

def make_ingredient_text(name):
    recipe = get_recipe_detail(name)
    if recipe is None:
        return ["레시피를 찾을 수 없습니다."]
    texts = []
    for item in recipe["ingredients"]:
        texts.append(item["name"] + " " + str(item["amount"]) + item["unit"])
    return texts

def make_detail_text(name):
    recipe = get_recipe_detail(name)
    if recipe is None:
        return ["레시피를 찾을 수 없습니다."]
    texts = []
    number = 1
    for step in recipe["steps"]:
        texts.append(str(number) + ". " + step)
        number += 1
    return texts

#테스트용
if __name__ == "__main__":
    urgent_items = ["두부","양파","파"]
    my_items = ["두부","양파","계란"]
    for text in make_result_text(urgent_items, my_items):
        print(text)

    print("----- 재료 -----")
    for text in make_ingredient_text("된장찌개"):
        print(text)

    print("----- 만드는 법 -----")
    for text in make_detail_text("된장찌개"):
        print(text)

