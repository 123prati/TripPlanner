# 🌍 WanderWise — AI Trip Planning Expert

A trip-planning chatbot built with **FastAPI**, **Azure OpenAI** (or Azure AI Foundry), and a self-contained single-page chat UI.

---

## ✨ Features

- **Expert Trip Planning Persona**: Generates day-by-day itineraries, estimated budgets, local dining suggestions, cultural etiquette, and packing checklists.
- **FastAPI Backend**: Clean and asynchronous REST API serving both the chat endpoint and the web UI.
- **Interactive Single-Page UI**: Clean interface with message bubbles, quick starter chips, dynamic "thinking..." animation, and auto-growing input.
- **Secure Configuration**: Validates environment settings with zero API key exposure in client responses or logs.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn
- **AI SDK**: OpenAI Python SDK (`openai>=1.20.0` with Azure support)
- **Frontend**: HTML5, Vanilla CSS, Vanilla JavaScript
- **Environment Management**: `python-dotenv`

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/123prati/TripPlanner.git
cd TripPlanner
```

### 2. Create and Activate Virtual Environment

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory (based on `.env.example`):

```env
AZURE_ENDPOINT=https://your-resource-name.services.ai.azure.com/api/projects/proj-default
AZURE_API_KEY=your_azure_api_key_here
AZURE_DEPLOYMENT=gpt-5-mini
AZURE_API_VERSION=2024-06-01
```

### 5. Run the Application

```bash
uvicorn app:app --reload --port 8000
```

Open your browser and navigate to **[http://localhost:8000](http://localhost:8000)**.

---

## 📄 License

MIT License.
