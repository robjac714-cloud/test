from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import spacy, re, requests

app = Flask(__name__)
CORS(app)  # مهم إذا الواجهة شغالة من localhost:5500

# -------- NLP --------
nlp = spacy.load("en_core_web_sm")

# ✅ spaCy v3+ correct way: add entity_ruler by name, then add patterns
ruler = nlp.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})
ruler.add_patterns([
    {"label": "CITY", "pattern": "Dubai"},
    {"label": "CITY", "pattern": "دبي"},
    {"label": "AREA", "pattern": "Dubai Marina"},
    {"label": "AREA", "pattern": "دبي مارينا"},
    {"label": "AREA", "pattern": "JVC"},
    {"label": "TYPE", "pattern": "apartment"},
    {"label": "TYPE", "pattern": "شقة"},
    {"label": "TYPE", "pattern": "villa"},
    {"label": "TYPE", "pattern": "فيلا"},
])

# -------- Reelly Config --------
REELLY_API = "https://search-listings-production.up.railway.app/v1/properties"
REELLY_API_KEY = os.getenv("REELLY_API_KEY", "")  # حطه كمتغير بيئة

# -------- Extractor --------
def extract_filters(text: str):
    doc = nlp(text)

    data = {
        "city": None,
        "area": None,
        "type": None,
        "beds": None,
        "min_price": None,
        "max_price": None
    }

    for ent in doc.ents:
        if ent.label_ == "CITY":
            data["city"] = ent.text
        elif ent.label_ == "AREA":
            data["area"] = ent.text
        elif ent.label_ == "TYPE":
            data["type"] = ent.text

    beds = re.search(r"(\d+)\s*(bed|beds|bedroom|غرفة|غرف)", text, re.I)
    if beds:
        data["beds"] = int(beds.group(1))

    price = re.search(
        r"(\d+(?:\.\d+)?)(k|m|ألف|مليون)?\s*[-–]\s*(\d+(?:\.\d+)?)(k|m|ألف|مليون)?",
        text,
        re.I
    )

    def parse_price(n, u):
        n = float(n)
        if not u:
            return int(n)
        u = u.lower()
        if u in ["k", "ألف"]:
            return int(n * 1_000)
        if u in ["m", "مليون"]:
            return int(n * 1_000_000)
        return int(n)

    if price:
        data["min_price"] = parse_price(price.group(1), price.group(2))
        data["max_price"] = parse_price(price.group(3), price.group(4))

    return data

# -------- API --------
@app.post("/search")
def search():
    if not request.is_json:
        return jsonify({"ok": False, "error": "Expected JSON body"}), 400

    message = request.json.get("message", "")
    filters = extract_filters(message)

    # نظّف القيم الفاضية
    params = {k: v for k, v in filters.items() if v is not None}

    # إذا ما حطيت المفتاح، رجّع خطأ واضح
    if not REELLY_API_KEY:
        return jsonify({
            "ok": False,
            "error": "Missing REELLY_API_KEY. Set it as an environment variable.",
            "filters": filters
        }), 500

    r = requests.get(
        REELLY_API,
        params=params,
        headers={"x-api-key": REELLY_API_KEY},
        timeout=30
    )

    # لو Reelly رجّع خطأ
    if r.status_code >= 400:
        return jsonify({
            "ok": False,
            "status": r.status_code,
            "error": "Reelly API error",
            "details": r.text,
            "filters": filters
        }), 502

    return jsonify({
        "ok": True,
        "filters": filters,
        "results": r.json()
    })

if __name__ == "__main__":
    app.run(port=3000, debug=True)
