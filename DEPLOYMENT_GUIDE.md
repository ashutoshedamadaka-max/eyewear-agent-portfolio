# Implementation Guide: Vercel Backend + Lovable Frontend

Total time: ~3.5 hours. Total cost: ~₹50-100 in OpenAI usage.

## What you're building

```
┌─────────────────────┐         HTTPS          ┌──────────────────────────┐
│  Lovable Frontend   │  ────────────────────> │  Vercel Backend          │
│  (React/TS)         │   POST /api/chat       │  (FastAPI + agent.py)    │
│  yourapp.lovable.app│  <──────────────────── │  yourbackend.vercel.app  │
└─────────────────────┘                        └──────────────────────────┘
                                                          │
                                                          ▼
                                                ┌──────────────────┐
                                                │   OpenAI API     │
                                                └──────────────────┘
```

The OpenAI API key never touches the browser. Your visitors don't need their own keys.

---

## Phase 0: Prerequisites checklist

- [ ] OpenAI account with $5 in credits at platform.openai.com (mandatory before API works)
- [ ] GitHub account at github.com
- [ ] VS Code installed
- [ ] All project files downloaded (agent.py, eval_harness.py, lenskart_catalogue.json, vercel.json, requirements.txt, api/index.py, lovable_agent_ts.txt, README.md, .gitignore)

---

## Phase 1: Test locally first (30 min)

We're going to make sure everything works on your machine before putting it on the internet. Skipping this guarantees you'll waste time debugging cloud issues that have nothing to do with the cloud.

### 1.1 Open the project in VS Code

VS Code → File → Open Folder → pick the eyewear-agent-portfolio folder.

### 1.2 Install Python dependencies

Open VS Code Terminal (View → Terminal). Run:

```bash
pip install -r requirements.txt
pip install uvicorn
```

`uvicorn` is the local server we'll use to test the backend. It's not in requirements.txt because Vercel provides its own server.

### 1.3 Set your OpenAI key

**Mac/Linux:**
```bash
export OPENAI_API_KEY="sk-paste-your-key-here"
```

**Windows PowerShell:**
```powershell
$env:OPENAI_API_KEY="sk-paste-your-key-here"
```

### 1.4 Test the agent CLI (sanity check)

```bash
python agent.py
```

Try: "I need sunglasses for driving under 2500". You should see Specs respond. Type `quit` to exit.

### 1.5 Run the eval harness once

```bash
python eval_harness.py
```

This generates `eval_results.json` and `eval_report.md`. Costs ~₹5-10. Open `eval_report.md` and screenshot it - this is your portfolio data.

### 1.6 Test the backend locally

```bash
uvicorn api.index:app --reload --port 8000
```

You'll see "Uvicorn running on http://127.0.0.1:8000". Keep this terminal open.

In a new terminal:
```bash
curl http://127.0.0.1:8000/api/health
```

Expected response: `{"status":"ok","catalog_size":100,"openai_key_configured":true}`

Now test the chat endpoint:
```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"I need sunglasses for driving under 2500","history":[]}'
```

You should get a JSON response with Specs's reply and recommended_ids.

If this works, your backend is solid. Stop the server (Ctrl+C in the uvicorn terminal).

---

## Phase 2: Push to GitHub (15 min)

### 2.1 Create the GitHub repo

1. Go to github.com → click + → New repository
2. Name: `eyewear-agent-portfolio`
3. Public, no README
4. Click "Create repository"

### 2.2 Push your code

In VS Code terminal:
```bash
git init
git add .
git commit -m "Eyewear agent: backend + evals + Vercel config"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/eyewear-agent-portfolio.git
git push -u origin main
```

If git asks for credentials: use your GitHub username and a **personal access token** (GitHub → Settings → Developer settings → Personal access tokens → Generate new → check "repo" → copy token, use it as the password).

### 2.3 Verify on GitHub

Refresh your repo. You should see all files including `api/index.py`, `vercel.json`, `requirements.txt`, `eval_results.json`.

---

## Phase 3: Deploy backend to Vercel (30 min)

### 3.1 Sign up for Vercel

1. Go to vercel.com
2. Click "Sign Up" → use GitHub (easier; you already have an account)
3. Authorize Vercel to access your repos

### 3.2 Import your repo

1. From Vercel dashboard, click "Add New..." → "Project"
2. You'll see your GitHub repos. Find `eyewear-agent-portfolio` and click "Import"
3. Vercel auto-detects Python from `vercel.json` and `requirements.txt`. You should see "Other" or "Python" detected.
4. **DON'T deploy yet** - first add the environment variable

### 3.3 Add the OpenAI API key as an env var

On the import screen, scroll down to "Environment Variables":

- **Name:** `OPENAI_API_KEY`
- **Value:** your OpenAI API key (sk-...)
- Click "Add"

Make sure it's set for "Production", "Preview", and "Development" (default).

### 3.4 Deploy

Click "Deploy". Wait 1-2 minutes. You'll see a build log scrolling. When done:

- You'll get a URL like `eyewear-agent-portfolio-yourname.vercel.app`
- **Copy this URL - you'll need it in Phase 4**

### 3.5 Verify deployment

Open `https://your-vercel-url/api/health` in a browser. You should see:
```json
{"status":"ok","catalog_size":100,"openai_key_configured":true}
```

If `openai_key_configured` is `false`: go to Vercel → Project → Settings → Environment Variables, double-check the key, redeploy.

If you see a 404 or 500: click your project in Vercel dashboard → Deployments → click the latest → "View Function Logs" to see Python errors.

### 3.6 Test the chat endpoint live

```bash
curl -X POST https://YOUR-VERCEL-URL/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"I need sunglasses for driving under 2500","history":[]}'
```

If you get a Specs reply with product IDs, **your backend is live on the internet**. Take a screenshot.

---

## Phase 4: Build the Lovable frontend (90 min)

### 4.1 Sign up for Lovable

1. Go to lovable.dev
2. Sign in with GitHub
3. Click "New Project" on the dashboard

### 4.2 Initial scaffold

Paste this prompt:

```
Build a chat interface for an eyewear shopping assistant called "Specs" — an AI agent with a quirky-expert personality that helps users pick eyewear from a Lenskart catalog.

The app calls a backend API at this URL: [PASTE YOUR VERCEL URL HERE]

Layout (desktop):
- Header: "Specs" logo on left, "View Eval Report" link on right
- Hero strip: tagline "Your friendly eyewear expert. Knows frames the way a sommelier knows wine." + 3 chip stats: "100 products", "13 eval cases", "10 quality metrics"
- Main area, two columns:
  - Left (60%): chat interface with message bubbles. User messages right-aligned blue (#2563eb), assistant left-aligned gray (#f3f4f6). Input box + send button at bottom.
  - Right (40%): "Recommended for you" panel showing up to 3 product cards. Each card: image, name, brand, price (₹), short description. Empty state: "Start chatting with Specs."
- Below chat: "Try an example" row with 3 clickable suggestion chips: "Sunglasses for driving under ₹2500", "Eyeglasses for office work", "Trendy sunglasses for parties"

Visual style: clean, modern, Lenskart-inspired. White background, subtle shadows on cards (shadow-sm), rounded corners (rounded-xl on cards, rounded-lg on bubbles), Inter font. Color palette: white background, slate-900 text, blue-600 primary, gray-100 surfaces.

Mobile responsive: chat full width, recommendations stack below in horizontal scroll.

Don't wire up the backend yet — just build the UI shell with this mock conversation:
- User: "I need sunglasses for driving"
- Assistant: "Polarized is what you want — kills the glare from other cars' windshields. What's your budget?"

And mock 2 product cards.
```

⚠️ **Replace `[PASTE YOUR VERCEL URL HERE]` with the actual URL from Phase 3.4 before submitting.**

Wait for Lovable to render. Iterate on visuals if needed.

### 4.3 Add the agent client

Tell Lovable:

```
Create a file src/lib/agent.ts. I'll paste the contents in the next message.

Then on the main page:
1. When the app loads, call fetchCatalog() once and store the catalog in state
2. When user sends a message, call generateResponse(message, history) — this hits the backend
3. Display the assistant's reply in the chat
4. Use the recommended_ids from the response to look up products in the catalog (using lookupProducts) and display them as cards in the right panel
5. Show a loading spinner in the chat while waiting for the response
6. Handle errors: display them as a system message in the chat
```

After Lovable creates the structure, send another message:

```
Replace the contents of src/lib/agent.ts with this code:
```

Then paste the entire contents of `lovable_agent_ts.txt` from your project folder.

### 4.4 Add the backend URL as a Lovable env var

In Lovable:

1. Click the gear icon / Project Settings
2. Find "Environment Variables" section
3. Add: `VITE_BACKEND_URL` = `https://YOUR-VERCEL-URL` (the one from Phase 3.4)
4. Save and redeploy preview

### 4.5 Test it!

In Lovable's preview:
1. Click a suggestion chip → wait → Specs should respond, products appear on right
2. Send a follow-up like "does the first one come in tortoise?" → Specs should answer in context

If it doesn't work, the most common issue is CORS. Tell Lovable: "When I make a request, I get a CORS error. Make sure the fetch includes proper headers and the backend URL is correct."

If you still see CORS issues, double-check Phase 3 — the FastAPI CORS middleware should handle this.

### 4.6 Build the eval page

Tell Lovable:

```
Add a route at /evals that displays evaluation results.

When the page loads, call fetchEvalResults() — it fetches data from the backend.

Layout:
- Page title: "Evaluation Report - Specs v3"
- Subhead: "We test the agent on 13 scenarios across 10 quality metrics."
- Top: 4 metric cards showing pass rates: Catalog Adherence, Budget Adherence, Avg Use-Case Fit (LLM judge, /5), Personality Consistency (LLM judge, /5). Calculate from the JSON.
- Middle: A table of all test cases. Columns: Test ID, Description, PASS/FAIL badges per metric, Latency.
  - Pass = green check, Fail = red X, N/A = gray dash
  - Click any row to expand showing: user turns, agent reply, LLM judge reasoning
- Bottom: Methodology section explaining each metric

Add navigation links in the header: "Demo" and "Eval Report".
```

### 4.7 Polish + publish

```
Final polish:
1. Footer with: "Built by [YOUR NAME] | View source on GitHub: [YOUR-GITHUB-URL] | LinkedIn"
2. Add an "About" modal accessible from an info icon: explain the architecture (Lovable frontend, Vercel Python backend, OpenAI gpt-4o-mini), and 3 key design decisions (pre-filter before LLM, three-path conversation, personality with banned-phrase check)
3. Smooth animations: products slide in from right when recommended
4. Add "Clear chat" button below input
```

Click "Publish" in Lovable. You get a `*.lovable.app` URL.

---

## Phase 5: Final verification (15 min)

### 5.1 End-to-end test on the live URL

1. Open your Lovable URL in incognito mode (no cached state)
2. Click each suggestion chip — verify products appear
3. Try multi-turn: "I need glasses" → answer Specs's question → get recs → ask follow-up
4. Try the impossible budget case: "sunglasses under 500" — verify Specs is honest, doesn't invent
5. Visit /evals — verify the eval page renders with real data

### 5.2 Check that nothing leaks the API key

1. Open browser DevTools (F12) → Network tab
2. Send a chat message
3. Click the request to your-backend.vercel.app/api/chat
4. Check Headers — there should be NO Authorization header with your OpenAI key
5. The OpenAI call happens server-side; the browser only sees your Vercel domain

This is the security win of Option C. Mention it in your case study.

### 5.3 Set a Vercel spending limit

To avoid surprise bills if your demo goes viral or someone abuses it:

1. Vercel dashboard → Settings → Usage → Spend Management
2. Set a monthly limit you're comfortable with (e.g. $5)

### 5.4 Set OpenAI usage limits too

1. platform.openai.com → Settings → Limits
2. Set monthly hard limit at $10
3. Set soft limit (email warning) at $5

---

## Phase 6: Portfolio (45 min)

### 6.1 Record a Loom

60-90 seconds showing:
- Open your Lovable URL
- Click suggestion chip → Specs recommends, products appear
- Send follow-up "does it come in tortoise?" → context preserved
- Try impossible budget → honest no-match
- Click "Eval Report" → scroll metrics

### 6.2 LinkedIn post

> Built a conversational AI shopping agent for eyewear over a 100-product catalog with a real client/server architecture.
>
> 🏗️ Stack:
> - Python/FastAPI backend on Vercel (handles agent logic, hides OpenAI key server-side)
> - React frontend on Lovable
> - 13-test eval harness with 10 quality metrics (rule-based + LLM-as-judge)
>
> 🎯 PM-flavored decisions:
> - Pre-filtered catalog with rules before LLM calls (no vector DB needed at this scale)
> - Three-path conversation flow: classifier routes new searches vs follow-ups vs smalltalk
> - Designed "Specs" character with centralized voice spec + deterministic banned-phrase guardrail
> - Server-side API key + rate limiting so visitors can chat without bringing their own key
>
> 📊 Eval results: [X]/13 tests passing. Catalog adherence 100% (zero hallucinated products).
>
> 🔗 Live demo: [your-lovable-url]
> 📂 Code: [your-github-url]
> 🎥 60s walkthrough: [your-loom-url]
>
> Total cost to build: ~₹100 in API usage. Built in a weekend.

### 6.3 Resume entry

> **Specs - Conversational AI for Eyewear Shopping** *(2026)*
> Built a multi-turn shopping agent over a 100-product catalog with classifier-first three-path architecture and 10-metric eval harness. Designed Python/FastAPI backend on Vercel with server-side API key handling and rate limiting; React frontend on Lovable. [X]/13 eval tests passing including 100% catalog adherence.
> *Stack: OpenAI gpt-4o-mini, FastAPI, Vercel, TypeScript/React, Python evals*

---

## Common gotchas

**"Vercel build fails with 'No module named agent'"**
The vercel.json route config might not be pulling parent files into the build. Solution: in api/index.py the `sys.path.insert` line should fix this. If not, copy `agent.py` and `lenskart_catalogue.json` into the `/api` folder too and update the import path.

**"CORS error in Lovable when calling backend"**
The FastAPI CORSMiddleware is set to `allow_origins=["*"]`. If you still see issues, the most likely cause is the request being blocked at network level. Check that VITE_BACKEND_URL in Lovable matches your Vercel URL exactly (including https://).

**"OpenAI key configured: false in /api/health"**
Env var didn't propagate. Vercel Project → Settings → Environment Variables → verify it's there. Then redeploy: Deployments tab → click latest → "Redeploy".

**"Rate limit hits but I'm the only one using it"**
The in-memory rate limit doesn't reset between Vercel cold starts but might appear inconsistent. For production, swap to Vercel KV or Upstash Redis. For demo, restart the Vercel deployment to reset.

**"Lovable preview shows 'Couldn't reach the backend'"**
VITE_BACKEND_URL not set in Lovable env vars, or set incorrectly. Project Settings → Environment Variables → verify it.

**"My OpenAI bill is climbing fast"**
The rate limit is per IP. If you've made it BYOK in Lovable instead, this isn't the issue — but if you've kept the server-side key (Option C), tighten the rate limit in `api/index.py` (change `_RATE_LIMIT = 30` to a lower number).

---

## What's different from "just Lovable" (Option A)

| | Option A (Lovable only) | Option C (this guide) |
|---|---|---|
| Backend | None — agent runs in browser | Python/FastAPI on Vercel |
| API key | In browser (visitors bring own) | On server, hidden |
| Setup time | 90 min | 3.5 hrs |
| Looks more pro | Decent | Definitely |
| Resume signal | "Built AI agent in Lovable" | "Built AI backend on Vercel + frontend on Lovable" |

The portfolio difference is real. Option C demonstrates you can actually build full-stack systems, not just prompt a UI builder.

---

## Done? Send me your live URL.

Once it's deployed, send me the Vercel and Lovable URLs. I can review the deployed version and suggest tweaks before you put it on your resume.
