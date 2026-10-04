import os, requests
def summary(name, a, lang):
    prompt = (f"Write exactly 3 short, plain-language sentences in {lang} for the parent of {name}. "
              f"Data: attendance {a['att']}%, average test score {a['avg']}/100, assignments submitted on average "
              f"{a['late']} days late (negative = early), predicted final exam score {a['pred']}/100, at risk: {a['risk']}. "
              "Be encouraging and suggest one concrete action. Output only the 3 sentences.")
    key = os.getenv("GEMINI_API_KEY")
    if key:
        try:
            m = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              headers={"x-goog-api-key": key}, timeout=20,
                              json={"contents": [{"parts": [{"text": prompt}]}]})
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            pass
    return (f"{name} has {a['att']}% attendance and an average score of {a['avg']}/100. "
            f"The predicted final exam score is {a['pred']}/100. "
            + ("Please speak with the faculty soon so support can start early." if a["risk"]
               else "Keep up the good work and continue regular study."))

def gemini(prompt, fallback):
    key = os.getenv("GEMINI_API_KEY")
    if key:
        try:
            m = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              headers={"x-goog-api-key": key}, timeout=25, json={"contents": [{"parts": [{"text": prompt}]}]})
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            pass
    return fallback
