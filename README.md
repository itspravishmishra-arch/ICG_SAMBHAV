# Chat With Your Database

Ask questions about your data in plain English and get answers back.
No SQL knowledge needed.

```
You: How many customers do we have in each country?

Bot: India has the most customers (30), followed by Germany and the
     United States (9 each), then Canada and the United Kingdom (6 each).

  SQL: SELECT country, COUNT(*) AS customer_count FROM customers
       GROUP BY country ORDER BY customer_count DESC LIMIT 200
```

*(The numbers above are real for the included sample data. The exact wording
of the bot's answer and SQL will vary a little.)*

---

## Contents

1. [What is this?](#1-what-is-this)
2. [How it works](#2-how-it-works)
3. [What you need](#3-what-you-need)
4. [Setup, step by step](#4-setup-step-by-step)
5. [Choose your AI service (free options)](#5-choose-your-ai-service-free-options)
6. [Try it with the sample data](#6-try-it-with-the-sample-data)
7. [Use your own database](#7-use-your-own-database)
8. [All commands](#8-all-commands)
9. [Talking to the bot](#9-talking-to-the-bot)
10. [The notes folder (OKF) and how to make answers better](#10-the-notes-folder-okf-and-how-to-make-answers-better)
11. [Safety](#11-safety)
12. [Privacy and cost](#12-privacy-and-cost)
13. [Troubleshooting](#13-troubleshooting)
14. [Questions people ask](#14-questions-people-ask)
15. [What is in each file](#15-what-is-in-each-file)
16. [For developers](#16-for-developers)
17. [Limits](#17-limits)
18. [Words explained](#18-words-explained)

---

## 1. What is this?

Most company data sits in a **database**. To get answers out of it, someone
normally has to write **SQL**, a special language for asking databases questions.

This project lets you type a normal question instead. It:

1. works out which parts of the database matter for your question,
2. writes the SQL for you,
3. checks that the SQL is safe (read-only),
4. runs it,
5. explains the result in plain English.

It has two programs:

| Program | What it does | How often you run it |
|---|---|---|
| `okf_generator.py` | Looks at your database and writes a folder of short notes about each table. | Once at the start, and again when the database changes. |
| `rag_sql_chatbot.py` | The chatbot you talk to. It reads those notes to understand your data. | Every time you want to ask questions. |

There is also a helper, `create_sample_db.py`, which makes a fake shop database
so you can try everything without using real data.

---

## 2. How it works

Think of a big library (your database) with hundreds of shelves (tables).
A helper could read every shelf label before every question, but that would be
slow and confusing. So:

- **Step A (once):** the generator makes an index card for every shelf: what it
  holds, what its columns mean, and which other shelves it connects to.
  This folder of cards is called the **OKF bundle** (see section 10).
- **Step B (every question):** the chatbot searches the cards for the shelves
  that match your question, also grabs the shelves connected to them, and gives
  only those cards to an AI model (OpenAI, Google Gemini, or one running on your own
  computer). The AI writes the SQL.

```
Your question
    │
    ▼
(follow-up? rewrite it so it makes sense alone)
    │
    ▼
Find the matching tables + the tables connected to them
    │
    ▼
AI writes the SQL
    │
    ▼
Safety check (one read-only SELECT, known tables only, row limit)
    │
    ▼
Run it on the database (read-only)
    │        └── if it fails: AI fixes the SQL and tries again (up to 2 times)
    ▼
AI explains the result in plain English
```

---

## 3. What you need

- A computer with **Python 3.10 or newer**. Check with `python --version`
  (on Mac/Linux you may need `python3 --version`). Get Python from python.org.
- An **AI service** that writes the SQL. Pick one: an OpenAI API key (needs credit),
  a free Google Gemini key, or Ollama (free, runs on your own computer). See
  [section 5](#5-choose-your-ai-service-free-options). OpenAI's API costs money, and new
  accounts need credit added first.
- A **database** to ask questions about. You can start with the free sample
  database included here (section 6).
- A **terminal**: Terminal on Mac, Command Prompt or PowerShell on Windows.

---

## 4. Setup, step by step

Do this once.

**1. Open a terminal inside the project folder.**

```bash
cd text2sql-okf-chatbot
```

Run every command in this README from this folder.

**2. Create a private Python environment** (keeps this project's packages separate):

| | Mac / Linux | Windows |
|---|---|---|
| Create | `python3 -m venv .venv` | `py -m venv .venv` |
| Turn on | `source .venv/bin/activate` | `.venv\Scripts\activate` |

When it is on, your terminal line starts with `(.venv)`. You need to turn it on
again each time you open a new terminal.

**3. Install what the project needs:**

```bash
pip install -r requirements.txt
```

**4. Create your settings file.** Copy `.env.example` to a new file named `.env`:

| Mac / Linux | Windows |
|---|---|
| `cp .env.example .env` | `copy .env.example .env` |

> Files starting with a dot are hidden on Mac and Linux. To see them, press
> `Cmd + Shift + .` in Finder, or run `ls -a` in the terminal.

**5. Open `.env` in any text editor** and set your AI service and key. For OpenAI:

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-real-key-here
DATABASE_URL=sqlite:///sample_shop.db
```

No OpenAI credit? Use a free option instead: follow section 5 below.

Save the file. Keep `.env` private: never share it or put it on GitHub.
(It is already excluded by `.gitignore`.)

---

## 5. Choose your AI service (free options)

The program needs an AI service to write the SQL and explain the results. Pick **one**.
You choose it with `LLM_PROVIDER` in `.env` (or per command with `--provider`).

| | **OpenAI** | **Google Gemini** | **Ollama** |
|---|---|---|---|
| Cost | Pay as you go; a new account needs credit added | Has a free tier (limits and free models change) | Free |
| Runs on | OpenAI's servers | Google's servers | Your own computer |
| You need | An API key with credit | A free API key | Ollama installed and two models downloaded |
| Privacy | Your question and the query results are sent to OpenAI | On the free tier, Google may use what you send to improve its products. **Do not use client or confidential data.** | Nothing leaves your computer |
| Extra install | none | `pip install langchain-google-genai` | `pip install langchain-ollama` |
| Quality | Depends on the model you pick; bigger models are more reliable | Same | Same; small local models make more SQL mistakes |

### Option A: OpenAI

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

Create a key at <https://platform.openai.com/api-keys> and add credit under Billing.
To keep costs low while testing, add `--chat-model gpt-4o-mini` to the chatbot command.

### Option B: Google Gemini (free tier)

1. Install the extra package: `pip install langchain-google-genai`
2. Create a free key in Google AI Studio: <https://aistudio.google.com/apikey>
3. Put this in `.env`:

```
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your-key-here
```

Things to know:

- The free tier has small per-minute and per-day request limits, and Google changes them
  often. Each question makes 2 to 4 requests, so you may see a rate-limit message. Wait a
  minute and try again.
- Which Gemini models are free also changes. The defaults are `gemini-flash-latest` (chat)
  and `gemini-embedding-001` (search). If you see "model not found", run
  `python rag_sql_chatbot.py --provider gemini --list-models` and pass a name with
  `--chat-model` or `--embedding-model`.
- Do not use real client data on the free tier (see the table above).

### Option C: Ollama (free, on your computer)

1. Install Ollama from <https://ollama.com>.
2. Download two models (one-time, large downloads):

```bash
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

3. Install the extra package: `pip install langchain-ollama`
4. Make sure Ollama is running (the desktop app, or `ollama serve` in another terminal).
5. Put this in `.env`:

```
LLM_PROVIDER=ollama
```

Things to know:

- A model of this size usually needs roughly 8 GB of free memory and is slow on computers
  without a good graphics card. Smaller models make more SQL mistakes.
- To try another model, download it with `ollama pull NAME` and pass `--chat-model NAME`.
- Nothing leaves your computer, so this is the safest choice for private data.

### See which models you can use

```bash
python rag_sql_chatbot.py --provider gemini --list-models
```

(Use `openai` or `ollama` in place of `gemini` for the others.)

### Switching later

Change `LLM_PROVIDER` (and add that service's key) in `.env`. Nothing else needs to be
redone: the notes folder works with every service, and the search index is rebuilt in
memory at each start. If you do not want an AI service to draft the table descriptions,
use `python okf_generator.py --no-enrich`.

---

## 6. Try it with the sample data

This takes about five minutes and uses fake data, so nothing real is at risk.

```bash
python create_sample_db.py
python okf_generator.py --output okf_bundle_sample
python rag_sql_chatbot.py --bundle okf_bundle_sample
```

What each line does:

1. **Makes a fake online-shop database** in a file called `sample_shop.db`
   (60 customers, 24 products, 400 orders, reviews, and so on).
2. **Writes the notes folder** `okf_bundle_sample` describing those tables.
3. **Starts the chatbot.** After a short start-up it shows `You:` and waits.

These commands use the AI service you chose in `.env`.

Questions to try:

- How many customers do we have in each country?
- What are the top 5 products by revenue?
- Which customers have placed more than 8 orders?
- What is the average rating per category?
- Then a follow-up: *And only for delivered orders?*

Type `exit` to quit.

---

## 7. Use your own database

### Step 1: Tell the project where the database is

Open `.env` and set `DATABASE_URL`. This is the database's **address**.

| Database | Address format | Extra install |
|---|---|---|
| SQLite (a single file) | `sqlite:///file.db` (a file in the project folder) or `sqlite:////full/path/file.db` (four slashes for a full path) | none |
| PostgreSQL | `postgresql+psycopg2://username:password@host:5432/dbname` | `pip install psycopg2-binary` |
| MySQL | `mysql+pymysql://username:password@host:3306/dbname` | `pip install pymysql` |

PostgreSQL and SQLite are the ones this project was written for. MySQL
should work but has not been tested.

**MongoDB and other non-SQL databases are not supported.**

Tips:

- If your password contains special characters such as `@`, `:` or `/`, write them in
  coded form (for example `@` becomes `%40`), or the address will be misread.
- The database stays where it is (your server, or a hosted service). This project only
  needs its address. You do not copy any data into the project.
- If the database is on a company server, you may need to ask the administrator to
  allow your connection.

### Step 2: Use a read-only database user (important)

Ask the database administrator for a user that can **only read**. This is
the strongest protection against accidents. The program also checks every
query itself (section 11), but a read-only user is the real safety net.

### Step 3: Generate the notes

```bash
python okf_generator.py --output okf_bundle
```

### Step 4: Review the notes (see section 10)

### Step 5: Start the chatbot

```bash
python rag_sql_chatbot.py --bundle okf_bundle
```

### Free online database for testing

If you want a hosted database without paying, Neon and Supabase both offer free
PostgreSQL plans (limits change, so check their websites). Sign up, create a
database, and copy the connection address they give you. Then:

```bash
pip install psycopg2-binary
python create_sample_db.py --database-url "postgresql+psycopg2://user:pass@host/db?sslmode=require"
```

This loads the fake shop data into that online database. Next, put the same address
in `.env` as `DATABASE_URL`, and continue from "Step 3: Generate the notes" above.

`create_sample_db.py` refuses to touch tables that already exist unless you add
`--force`, which **erases** them. Never use `--force` on a database with real data.

---

## 8. All commands

Run from the project folder, with `.venv` turned on.

### `python create_sample_db.py`  (make fake test data)

| Option | Meaning |
|---|---|
| `--database-url URL` | Where to create it. Default: `sqlite:///sample_shop.db` |
| `--force` | Delete and recreate the sample tables if they exist |

### `python okf_generator.py`  (write the notes folder)

| Option | Meaning |
|---|---|
| `--database-url URL` | Database address. Default: `DATABASE_URL` from `.env` |
| `--output FOLDER` | Where to write the notes. Default: `okf_bundle` |
| `--sample-rows N` | Copy N real rows per table into the notes. Default: `0` (none, for privacy) |
| `--no-enrich` | Do not use an AI service; write plain descriptions instead |
| `--provider NAME` | AI service for the descriptions: `openai`, `gemini` or `ollama`. Default: `LLM_PROVIDER` from `.env`, else `openai` |
| `--model NAME` | Model used to draft descriptions. Default depends on the provider |

### `python rag_sql_chatbot.py`  (the chatbot)

| Option | Meaning |
|---|---|
| `--database-url URL` | Database address. Default: `DATABASE_URL` from `.env` |
| `--bundle FOLDER` | Notes folder from the generator. Default: `okf_bundle` |
| `--provider NAME` | AI service: `openai`, `gemini` or `ollama`. Default: `LLM_PROVIDER` from `.env`, else `openai` |
| `--chat-model NAME` | Model that writes SQL and answers. Default depends on the provider (`gpt-4o`, `gemini-flash-latest`, `qwen2.5-coder:7b`) |
| `--embedding-model NAME` | Model used to search the notes. Default depends on the provider (`text-embedding-3-small`, `gemini-embedding-001`, `nomic-embed-text`) |
| `--list-models` | Show the models you can use with this provider, then exit |
| `--top-k N` | How many tables the search picks per question. Default: `5` |
| `--max-tables N` | Most tables shown to the AI per question. Default: `10` |
| `--max-rows N` | Most rows read from a result. Default: `200` |
| `--hide-sql` | Do not print the SQL under each answer |

### Other

| Command | What it does |
|---|---|
| `pytest` | Run the automated tests (no API key or internet needed) |
| `pip install -r requirements.txt` | Install the packages |

### Settings you can put in `.env`

| Setting | Meaning |
|---|---|
| `LLM_PROVIDER` | `openai`, `gemini` or `ollama` |
| `OPENAI_API_KEY` | Your OpenAI key (when using OpenAI) |
| `GOOGLE_API_KEY` | Your Gemini key (when using Gemini; `GEMINI_API_KEY` also works) |
| `OLLAMA_BASE_URL` | Where Ollama is running. Default: `http://localhost:11434` |
| `DATABASE_URL` | The database address |
| `CHAT_MODEL` | Same as `--chat-model` (use a name that belongs to your provider) |
| `EMBEDDING_MODEL` | Same as `--embedding-model` |
| `OKF_MODEL` | Same as the generator's `--model` |

Options typed on the command line win over `.env`.

---

## 9. Talking to the bot

- Ask normal questions: *"Which products are low on stock?"*
- **Follow-ups work.** The bot remembers the last few questions: *"And in Germany?"*
- Under each answer you see the **SQL** it ran and a preview of the **rows** (first 10).
  Seeing the SQL helps you check that the bot understood you. Hide it with `--hide-sql`.
- Commands inside the chat:

| Type this | What happens |
|---|---|
| `/reset` | Forget the conversation and start fresh |
| `exit` or `quit` | Leave the chatbot |

Tips for better answers:

- Be specific: *"total revenue in 2026 by month"* beats *"sales info"*.
- If the bot says it can't answer, the data may not be in the database, or the notes
  may not describe it well (section 10).
- If an answer looks wrong, read the SQL. It usually shows what went wrong.

---

## 10. The notes folder (OKF) and how to make answers better

### What it is

**OKF** stands for *Open Knowledge Format*, an open way of writing down knowledge as
plain text files, published by Google Cloud. The generator uses it to create one small
file per table, such as `okf_bundle/orders.md`. Think of each file as an index card.

Each card has:

- **A header** with the table's name, a one-line description, tags, a trust label, and
  its connections to other tables.
- **A readable body** with the description, a table of columns, a list of related tables
  (with links and the exact way to join them), and a **Notes** section for people.

There is also an `index.md` listing all the cards.

OKF is **not** a database and holds none of your actual data. It only holds notes *about* the data.

### Why bother?

- The AI can only write good SQL if it understands what your tables mean.
- The notes are plain files, so non-technical people can read and fix them in any text editor.
- They can be saved in GitHub, so changes are tracked and reviewed.

### Improve the answers: review the notes

The first descriptions are drafted by an AI from column names alone, so they can be
wrong or vague. Each file starts with the label `trust_tier: unverified` to show this.

1. Open the files in `okf_bundle/`.
2. Fix any wrong description at the top.
3. Under the **`## Notes`** heading, write what the AI cannot guess, for example:
   - *"status is one of: pending, shipped, delivered, cancelled"*
   - *"amounts are in US dollars"*
   - *"a customer with no orders is not an active customer"*
4. Change `trust_tier: unverified` to `trust_tier: human-reviewed` in that file.

The chatbot reads your Notes text on every question, so this is the single best way to
improve accuracy.

### When the database changes

Run the generator again:

```bash
python okf_generator.py --output okf_bundle
```

Files you marked `human-reviewed` keep your description and tags, and everything under
**Notes** is always kept. The structure (columns, connections) is refreshed. If a table
was removed from the database, the generator warns you about its leftover file.

### A note on the format

Some header fields (`sql:` with keys and connections) are this project's own
additions, which OKF allows, but other OKF tools will not understand them.
The names `trust_tier` and `generated` follow public descriptions of OKF version 0.2.
For exact rules read the official spec:
<https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>

---

## 11. Safety

The program is built to only ever **read** data:

- Only **one SELECT** query is allowed. Anything that changes data (insert, update,
  delete, drop, and so on), even hidden inside another query, is blocked.
- Only tables listed in the notes folder may be used.
- A row limit is added to every query, and at most 200 rows are read.
- SQLite connections are set to read-only. PostgreSQL connections get a 15-second
  time limit and a read-only default.
- If the AI writes a bad query, it is shown the error and gets up to 2 chances to fix it.

**Still required: use a read-only database user.** Some database functions (for example
ones that make the database pause) are not blocked by the program's checks, and
the read-only settings for databases other than SQLite and PostgreSQL are not built in.

---

## 12. Privacy and cost

### What leaves your computer

The chatbot sends this to the AI service you chose (OpenAI or Google Gemini):

- your question and the recent conversation,
- the descriptions and column lists of the tables it picked,
- the SQL it wrote,
- **the rows the query returned** (so the answer can be written).

The notes folder contains no real data unless you used `--sample-rows`.

With **Ollama**, none of this leaves your computer.

> If the data belongs to a client or a company, check that they are happy for it to
> be processed by OpenAI or Google before using real data. On Gemini's free tier, Google
> may use prompts and answers to improve its products, so use only sample or public data there.

### Cost

Every question makes a few AI calls (rewrite, SQL, maybe retries, answer), and starting
the chatbot makes a few more to read the notes. Generating notes uses one call per table.

- **OpenAI** charges per use. Each call is small, but it adds up. Check current prices and
  set a monthly spending limit in your OpenAI account.
- **Gemini** is free within its limits; check Google's current limits.
- **Ollama** is free but uses your computer's memory and processor.

---

## 13. Troubleshooting

| What you see | What it means and what to do |
|---|---|
| `No API key found for 'openai'` (or `'gemini'`) | The key is missing. Check `.env` exists (not just `.env.example`), is in the project folder, and the line reads `OPENAI_API_KEY=sk-...` (or `GOOGLE_API_KEY=...`) with no spaces or quotes. Also check `LLM_PROVIDER` matches the service whose key you set. |
| `Unknown provider ...` | `LLM_PROVIDER` or `--provider` must be `openai`, `gemini` or `ollama`. |
| `The package for 'gemini' is not installed. Run: pip install ...` | Run the command it shows (`langchain-google-genai` for Gemini, `langchain-ollama` for Ollama). |
| `Could not reach Ollama ... Is it running?` | Start Ollama (the desktop app, or `ollama serve`) and try again. |
| `Set DATABASE_URL ...` | Add `DATABASE_URL=...` to `.env`, or pass `--database-url`. |
| `No table files found in 'okf_bundle'. Run okf_generator.py first.` | The notes folder is empty or the name is wrong. Run the generator, and make sure `--bundle` matches the folder you generated. |
| `command not found: python` / `'python' is not recognized` | Try `python3` (Mac/Linux) or `py` (Windows). If neither works, install Python. |
| `ModuleNotFoundError: No module named ...` | The packages are not installed or `.venv` is off. Turn on `.venv` (section 4) and run `pip install -r requirements.txt`. |
| `No module named 'psycopg2'` | Run `pip install psycopg2-binary` (PostgreSQL). |
| Cannot connect / timeout / `could not translate host name` | Wrong address, wrong password, or the database does not allow your connection. Check `DATABASE_URL`, special characters in the password, and firewall or VPN rules. |
| `Something went wrong: ...` mentioning authentication, `401` or `403` | The API key is wrong, expired or lacks permission. Create a new one. |
| `Something went wrong: ...` mentioning quota, billing, `429` or rate limit | OpenAI: no credit left, add some. Gemini: you hit the free limit, wait a minute and retry. |
| `Something went wrong: ...` mentioning the model is not found | That model name is not available to you. Run `--list-models`, then pass a valid name with `--chat-model` or `--embedding-model`. For Ollama, download it first with `ollama pull NAME`. |
| `Hint: ...` lines under an error | The program recognised a common problem and suggests a fix. Follow it. |
| `These tables already exist` (sample data script) | The sample tables are already there. Use `--force` only if you are sure they can be erased. |
| Bot says *"I can't answer that from the data I have access to"* | The data is not in the database, or the notes do not describe it. Improve the notes (section 10). |
| Bot says *"I couldn't build a query that works"* | The AI failed after 3 tries. Rephrase the question, or add clearer notes. The error is shown under the answer. |
| The answer looks wrong | Read the SQL under the answer. Add a note explaining the confusing column or value. |
| Start-up is slow | It reads the notes and creates searchable versions of them each time. Very large databases take longer. |

---

## 14. Questions people ask

**Do I need to know SQL or Python?**
No SQL. For setup you only copy and paste the commands above.

**Does it change my data?**
It is designed not to (section 11). Using a read-only database user makes that certain.

**Can it work with MongoDB?**
No. It is built for SQL databases. MongoDB would need a different approach.

**Do I need to run the generator every time?**
No. Once at the start and again when the database structure changes.

**Should I commit `okf_bundle/` to GitHub?**
Yes, that is the point. Descriptions and notes get saved and reviewed like code.
Check first that they contain nothing sensitive. Do not commit `.env` or `.db` files
(both are already excluded).

**Can I use something other than OpenAI?**
Yes. Google Gemini (free tier) and Ollama (free, on your computer) are built in; see
section 5. Other LangChain-supported services can be added in `providers.py`.

**Is it always right?**
No. AI can misunderstand a question or a column. Read the SQL, and keep a list of
important questions with known answers to check after changes.

---

## 15. What is in each file

```
text2sql-okf-chatbot/
├── README.md              this guide
├── requirements.txt       the Python packages to install
├── .env.example           template for your settings (copy to .env)
├── .gitignore             keeps secrets and test files out of GitHub
├── pytest.ini             test settings
│
├── okf_generator.py       database  ──►  notes folder (OKF bundle)
├── rag_sql_chatbot.py     notes + your question  ──►  SQL  ──►  answer
├── providers.py           picks OpenAI, Gemini or Ollama; lists models; explains errors
├── okf_utils.py           small helpers for reading and writing the notes
├── create_sample_db.py    makes the fake shop database
│
└── tests/                 automated tests (run with: pytest)
    ├── test_validator.py      safety checks on SQL
    ├── test_pipeline.py       whole flow with a pretend AI
    └── test_providers.py      AI service choices, model lists, error hints
```

---

## 16. For developers

**Main pieces in `rag_sql_chatbot.py`**

| Piece | Job |
|---|---|
| `load_tables` | Reads the notes folder into table objects |
| `Text2SQLBot.retrieve` | Embedding search for the best tables, then adds tables linked by foreign keys |
| `validate_sql` | Parses with sqlglot: one read-only query, no write operations anywhere inside it, only known tables (names from `WITH` clauses are allowed) |
| `apply_row_limit` | Adds `LIMIT` if missing |
| `make_engine` | Opens the database; read-only for SQLite, timeout and read-only default for PostgreSQL |
| `Text2SQLBot.ask` | The full flow including retries and conversation history |
| `providers.make_llm` / `make_embeddings` | Build the chat and embedding models for the chosen service |

The LangChain parts are small: four prompt templates, each joined to the model with
`prompt | llm | StrOutputParser()`, and an in-memory vector store for searching the notes.

**Tests.** `pytest` runs 65 offline tests using a fake AI model and fake embeddings.
They cover the safety checks, notes generation (including keeping human edits),
retrieval with foreign-key expansion, retries, read-only behaviour, follow-ups, and the
provider code (choosing a service, keys, building models, model lists, error hints).
They never call OpenAI, Gemini or Ollama, so run the sample data once with a real service
before relying on a new setup. In particular, the Gemini and Ollama paths were only
checked offline (the models are created and the code paths run with stand-ins), and the
default Gemini model names may need changing: use `--list-models`.

**Tested with:** Python 3.12, langchain-core 1.7, langchain-openai 1.7,
langchain-google-genai 4.4, langchain-ollama 1.1, SQLAlchemy 2.1, sqlglot 30.
If something breaks with other versions, try these.

**Adding another AI service.** `providers.py` is the only place that knows about specific
services. Add an entry to `REGISTRY`, and a branch in `make_llm`, `make_embeddings` and
`list_models`. The chatbot and generator only receive a LangChain chat model and an
embeddings object, so nothing else changes.

---

## 17. Limits

- Only the database's default schema is read, and only tables, not views.
- SQL databases only.
- Notes are searched in memory and rebuilt at each start. That suits hundreds of tables;
  for thousands, a saved search index would be better.
- Results are passed to the AI as text. A malicious value stored in a database could try
  to influence the answer. The prompt tells the AI to ignore instructions found in data,
  but this is not a guarantee.
- The bot does not draw charts. It returns text and a table.
- Free options have trade-offs: Gemini's free tier has small rate limits and may use your
  data to improve Google products; small Ollama models are slower and make more SQL mistakes.
- Answer quality depends on the quality of the notes.

---

## 18. Words explained

| Word | Meaning |
|---|---|
| **Database** | An organised store of data, usually in tables. |
| **Table** | A grid of rows and columns, like a spreadsheet tab (for example `customers`). |
| **SQL** | The language used to ask databases questions. |
| **Query** | One question written in SQL. |
| **Foreign key** | A link between tables, such as an order pointing to its customer. |
| **Join** | Combining rows from linked tables in one query. |
| **Read-only** | Allowed to look at data but never to change it. |
| **API key** | A secret password that lets a program use a service such as OpenAI. |
| **Environment file (`.env`)** | A private file holding settings and secrets for the project. |
| **Virtual environment (`.venv`)** | A private box of Python packages for one project. |
| **LLM** | Large language model, the kind of AI behind ChatGPT. |
| **LangChain** | A toolkit for building programs that use LLMs. |
| **RAG** | Retrieval-Augmented Generation: first find relevant information, then let the AI use it to answer. Here, the information found is the table notes. |
| **Embedding** | Turning text into numbers so a computer can find texts with similar meaning. |
| **OKF** | Open Knowledge Format: knowledge written as plain text files with a small structured header. |
| **Bundle** | A folder of OKF files. |
| **Trust tier** | A label saying how much to trust a note (`unverified`, or reviewed by a person). |
