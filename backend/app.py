from flask import Flask, request, jsonify
import spacy, re, requests
from spacy.pipeline import EntityRuler

app = Flask(__name__)

# -------- NLP --------
nlp = spacy.load("en_core_web_sm")
ruler = EntityRuler(nlp, overwrite_ents=True)

ruler.add_patterns([
    {"label": "CITY", "pattern": "Dubai"},
    {"label": "CITY", "pattern": "دبي"},
    {"label": "AREA", "pattern": "Dubai Marina"},
    {"label": "AREA", "pattern": "دبي مارينا"},
    {"label": "AREA", "pattern": "JVC"},
    {"label": "TYPE", "pattern": "apartment"},
    {"label": "TYPE", "pattern": "شقة"},
    {"label": "TYPE", "pattern": "villa"},
    {"label": "TYPE", "pattern": "فيلا"}
])

nlp.add_pipe(ruler, before="ner")

# -------- Reelly Config --------
REELLY_API = "https://search-listings-production.up.railway.app/v1/properties"
REELLY_API_KEY = "PUT_YOUR_REELLY_API_KEY_HERE"

# -------- Extractor --------
def extract_filters(text):
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

    beds = re.search(r"(\d+)\s*(bed|غرفة|غرف)", text, re.I)
    if beds:
        data["beds"] = int(beds.group(1))

    price = re.search(r"(\d+(?:\.\d+)?)(k|m)?\s*[-–]\s*(\d+(?:\.\d+)?)(k|m)?", text, re.I)

    def parse_price(n, u):
        n = float(n)
        if u == "k": return int(n * 1_000)
        if u == "m": return int(n * 1_000_000)
        return int(n)

    if price:
        data["min_price"] = parse_price(price.group(1), price.group(2))
        data["max_price"] = parse_price(price.group(3), price.group(4))

    return data

# -------- API --------
@app.post("/search")
def search():
    message = request.json.get("message", "")
    filters = extract_filters(message)

    params = {k:v for k,v in filters.items() if v}

    r = requests.get(
        REELLY_API,
        params=params,
        headers={"x-api-key": REELLY_API_KEY}
    )

    return jsonify({
        "filters": filters,
        "results": r.json()
    })

if __name__ == "__main__":
    app.run(port=3000, debug=True)
