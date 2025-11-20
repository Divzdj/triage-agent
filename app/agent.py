import os
import json
from typing import List, Dict, Any
import numpy as np
import time

# LLM client
try:
    import openai
except Exception:
    openai = None

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.schemas import KBMatch

# simple keyword-based fallback classifiers
CATEGORY_KEYWORDS = {
    "Billing": ["invoice", "bill", "payment", "charge", "refund", "billing"],
    "Login": ["login", "signin", "password", "authenticate", "2fa", "two-factor"],
    "Performance": ["slow", "latency", "timeout", "performance", "lag", "slowly"],
    "Bug": ["error", "exception", "500", "crash", "fail", "bug", "stacktrace"],
    "Question/How-To": ["how do", "how to", "documentation", "docs", "how-to", "question"],
}

SEVERITY_KEYWORDS = {
    "Critical": ["data loss", "security", "exposed", "down", "outage"],
    "High": ["cannot", "failure", "failed", "500", "crash", "blocked"],
    "Medium": ["errors", "intermittent", "timeout", "slow"],
    "Low": ["minor", "cosmetic", "question", "how to"],
}

DEFAULT_CATEGORY = "Other"



#  Safe LLM Wrapper (Retry)

def safe_llm_call(prompt, model_name, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=256,
                temperature=0.0,
            )
            return response["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"LLM call failed (attempt {attempt+1}): {e}")
            if attempt == retries - 1:
                return "LLM_ERROR"
            time.sleep(delay)


class TriageAgent:
    def __init__(self, kb_path="kb/kb.json", openai_api_key=None, model_name=None):
        self.kb = self._load_kb(kb_path)
        self.kb_docs = [self._kb_doc_text(e) for e in self.kb]
        self.vectorizer = TfidfVectorizer().fit(self.kb_docs) if self.kb_docs else None
        self.kb_vectors = self.vectorizer.transform(self.kb_docs) if self.vectorizer else None

        self.openai_api_key = openai_api_key
        self.model_name = model_name or "gpt-4o-mini"
        if openai and openai_api_key:
            openai.api_key = openai_api_key

    def _load_kb(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _kb_doc_text(self, entry):
        return " ".join([
            entry.get("title", ""),
            " ".join(entry.get("symptoms", [])),
            entry.get("category", ""),
            entry.get("recommended_action", "")
        ])

    # Search KB: returns top_k matches with scores
    def search_kb(self, query: str, top_k: int = 3) -> List[KBMatch]:
        if not self.vectorizer:
            return []

        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.kb_vectors).flatten()
        top_idx = sims.argsort()[::-1][:top_k]
        results = []
        for idx in top_idx:
            score = float(sims[idx])
            if score <= 0:
                continue
            e = self.kb[idx]
            results.append(KBMatch(
                id=e.get("id"),
                title=e.get("title"),
                score=round(score, 4),
                recommended_action=e.get("recommended_action")
            ))
        return results

    # LLM extraction with retries
    def call_llm_extract(self, description: str) -> Dict[str, str]:

        # If openai available, use safe LLM wrapper
        if openai and self.openai_api_key:
            prompt = (
                "You are a ticket triage assistant. "
                "Given the ticket description below, produce a JSON with keys: "
                "summary (1-2 sentences), "
                "category (Billing, Login, Performance, Bug, Question/How-To, Other), "
                "severity (Low, Medium, High, Critical). "
                "ONLY output JSON.\n\n"
                f"Description:\n{description}\n\nOutput JSON:"
            )

            llm_output = safe_llm_call(prompt, self.model_name)

            if llm_output == "LLM_ERROR":
                print("Using fallback extractor due to LLM failure.")
                return self.rule_based_extract(description)

            try:
                import re, json
                m = re.search(r"\{.*\}", llm_output, re.DOTALL)
                if m:
                    data = json.loads(m.group(0))
                else:
                    data = json.loads(llm_output)

                return {
                    "summary": data.get("summary", "").strip(),
                    "category": data.get("category", "Other"),
                    "severity": data.get("severity", "Low")
                }
            except Exception as e:
                print("JSON parsing error => fallback:", e)
                return self.rule_based_extract(description)

        # fallback if no LLM key
        return self.rule_based_extract(description)

    # fallback rule-based classification
    def rule_based_extract(self, description: str) -> Dict[str, str]:
        desc = description.lower()

        # category
        cat = DEFAULT_CATEGORY
        for c, kws in CATEGORY_KEYWORDS.items():
            if any(kw in desc for kw in kws):
                cat = c
                break

        # severity
        sev = "Low"
        for s, kws in SEVERITY_KEYWORDS.items():
            if any(kw in desc for kw in kws):
                sev = s
                break

        # summary
        summary = description.strip().split("\n")[0]
        if len(summary.split()) > 30:
            summary = " ".join(summary.split()[:25]) + "..."

        return {"summary": summary, "category": cat, "severity": sev}

    def decide_known_or_new(self, kb_matches: List[KBMatch], threshold=0.25) -> bool:
        if not kb_matches:
            return False
        return kb_matches[0].score >= threshold

    def suggest_next_step(self, known_issue: bool, kb_matches: List[KBMatch], severity: str) -> str:
        if known_issue and kb_matches:
            return (
                f"Attach KB article {kb_matches[0].id} and respond to user with troubleshooting steps. "
                f"If not resolved, escalate."
            )
        if severity in ["Critical", "High"]:
            return "Escalate to engineering immediately and request logs."
        return "Ask customer for more details such as screenshots, logs, and steps."

    def triage_ticket(self, description: str) -> Dict[str, Any]:
        extracted = self.call_llm_extract(description)
        kb_matches = self.search_kb(description, top_k=3)
        is_known = self.decide_known_or_new(kb_matches)
        next_step = self.suggest_next_step(is_known, kb_matches, extracted.get("severity", "Low"))

        return {
            "summary": extracted.get("summary", "").strip(),
            "category": extracted.get("category", "Other"),
            "severity": extracted.get("severity", "Low"),
            "known_issue": bool(is_known),
            "kb_matches": [m.dict() for m in kb_matches],
            "suggested_next_step": next_step
        }
