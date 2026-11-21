Actsistant
==========



# Database

On its first startup the app downloads the EU AI Act, chunks it, embeds the chunks with an embedding model served by Ollama and stores chunks and vectors in Weaviate. Later startups skip this because the collection is already populated. `cleanup.command` removes the Weaviate volume and the downloaded Act, so the next startup starts from scratch. Ollama has to be running whenever the app runs: the embedding model is needed to embed each question as well.

* Source: the official XHTML of Regulation (EU) 2024/1689 from the Publications Office (`publications.europa.eu/resource/celex/32024R1689`), kept as `src/database/eu_ai_act.xhtml`
* Chunking follows the structure of the Act: one chunk per recital, per numbered article paragraph (or per article when it has no numbered paragraphs) and per annex. Units longer than ~2 500 characters that consist of a list of points are split into one chunk per point, each prefixed with its lead-in text
* Weaviate collection `EuAiActChunk`, one object per chunk, with the properties `chunk_id` (e.g. `art_6.par_1`), `kind` (recital / article / annex), `heading` (citation, e.g. `Article 6(1)`), `title`, `chapter`, `section`, `article`, `paragraph`, `text` and `position`
* Vectors are computed by the app (the collection is configured for self-provided vectors) with `qwen3-embedding:0.6b`, pulled by `init.command`. The embedded text of a chunk is its heading and title followed by its text. Another Ollama model can be set with the `EMBEDDING_MODEL` environment variable; as vectors of different models cannot be compared, the model is recorded in the collection and a change rebuilds the collection on the next startup
* Retrieval is hybrid search: vector search on the embedded question combined with BM25 keyword search

# Agent

Questions are answered by a LangGraph agent (`src/core/agents/search_agent.py`) running a chat model served by Ollama, `qwen3:8b` by default (pulled by `init.command`; another Ollama model that supports tool calling can be set with the `CHAT_MODEL` environment variable). The first answer after a start takes longer because Ollama loads the model.

* The agent has one tool, `search_eu_ai_act` (`src/core/tools/search.py`), which runs the hybrid search described above and returns the matching passages with their citation headings
* The graph is the plain tool calling loop followed by a formatting step: the model is instructed to search before answering, the tool node runs the search, the model answers from the passages it got back, citing them inline by their bracketed heading, e.g. `[Article 6(1)]`, and a final `respond` node turns the conversation into a structured answer with the text and the headings of the sources. The model may search more than once; a recursion limit stops it from looping
* Of the retrieved passages, only those the structured answer names as sources are returned by `/api/ask` as `sources`, best ranked first. The schema of the structured answer is built per question and allows only the headings of the retrieved passages as sources, so the model cannot name a passage it has not seen; it can still attribute a claim to the wrong passage, which only an evaluation can catch. The retrieved and the cited headings are logged for every question
