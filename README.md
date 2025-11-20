# Support Ticket Triage Agent

A simple support ticket triage system using Python, FastAPI, and OpenAI GPT  with KB search. This project allows extracting ticket summary, category, severity, suggesting next steps, and identifying known issues.

---

## 1. How to run locally

### Prerequisites

* Python 3.10+
* pip (Python package manager)
* Optional: Docker for containerized deployment

### Install dependencies

```bash
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the root folder:

```env
OPENAI_API_KEY=<your_openai_api_key>
OPENAI_MODEL=gpt-4o-mini
KB_PATH=kb/kb.json
```

### Start the service

```bash
uvicorn main:app --reload
```

The API will run on: `http://127.0.0.1:8000`

### Test the `/triage` endpoint

Example curl request:

```bash
curl -X POST "http://127.0.0.1:8000/triage" \
-H "Content-Type: application/json" \
-d '{"description": "Checkout keeps failing with error 500 on mobile."}'
```

You can also open the **Swagger UI** to test endpoints:
`http://127.0.0.1:8000/docs`

---

## 2. Production Considerations

* **Deployment:** Can be containerized using Docker and deployed to AWS/GCP/Azure.
* **Configuration & secrets:** Use environment variables (`.env`) or secrets manager.
* **Logging & monitoring:** Log errors and requests; monitor request rates and API health.
* **Rate limiting:** Prevent abuse via in-memory rate limiting (currently 10 requests per 60s per IP).
* **Latency & cost:** LLM calls can be slow and cost money; caching or fallback to rule-based extraction reduces overhead.
* **Scaling:** Deploy behind a load balancer for higher traffic; consider async processing for LLM requests.

---

## 3. Agent Design

* **LLM Integration:**

  * Uses OpenAI GPT (default: `gpt-4o-mini`) to extract ticket summary, category, and severity.
  * If LLM fails, falls back to a simple **rule-based keyword classifier**.

* **KB Search:**

  * The knowledge base (KB) is stored as `kb/kb.json`.
  * Uses **TF-IDF vectorization** and cosine similarity to find top 3 matching known issues.
  * Determines whether the ticket is a `known_issue` or `new_issue` based on a similarity threshold.

* **Next step suggestion:**

  * If `known_issue`, attach the KB article.
  * For high severity or critical tickets, escalate to engineering.
  * Otherwise, request additional logs/screenshots from the user.

* **Trade-offs:**

  * Single-agent design (no complex multi-agent orchestration).
  * Rate-limiting is in-memory and not distributed; suitable for small-scale demo.
  * UI is minimal and static for simplicity; production would need proper frontend/backend separation.

---

## 4. Demo Notes 

* UI is available in `ui/index.html` for testing tickets locally.
* Submit ticket descriptions and see structured results in a table.
* Screenshots included in the repo:
    * Swagger Response: shows API response structure
    * Postman Collection: postman-collection.json for instant endpoint testing

---

