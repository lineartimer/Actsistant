Actsistant
==========

Actsistant is an AI tool that can answer questions on the EU AI Act. Currently in PoC stage.

# Architecture

## API

The api uses FastAPI's built-in mechanisms to verify the input.

## Database

The downloaded AI Act is stored in a [Weaviate](https://weaviate.io/) database.

Reasons for choosing Weaviate:
* Hybrid search in one call
* Weaviate is one of the established vector databases

The act is downloaded, chunked and embeddings are created on the first startup. This takes about a minute on a MacBook Pro.

### Chunking

The chunking follows the organic structure of the document: one unit of legal text (e.g. a paragraph) corresponds to one chunk. The heading of the text is stored in the chunk because it's often the heading that specifies what the text applies to.

With this design, there is no need for overlapping chunks, and one citation in the response will correspond to one unit of text in the act.

The downside is that chunk sizes vary, and for long chunks, the quality of the search might decrease but no chunks get truncated.

Also, lists are treated differently than regular text. Long lists are split into several chunks but the text directly preceding the list is added to each chunk. Reasons for this are:
* Units of texts containing lists can be very long
* Units of texts without a list center around one topic, whereas those with lists have diverse semantic meanings
* Staying within the context budget

Beyond the PoC level implementation, it might be worth measuring the performance of the search with different chunking strategies.

### Embeddings

The following embedding model is used: qwen3-embedding:0.6b. Reasons for selecting this model:
* The model is small enough to run on a laptop
* Benchmark quality is high for its size
* Permissive Apache 2.0 licence

# Limitations

* History not being kept
* No user management/authentication implemented

# Tests

As this is a PoC, the tool isn't being extensively tested.

Currently, there are tests for the following:
* Content of the database
* The search
* HTTP behavior of the API

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

# API

Questions are asked with `POST /api/ask` (`src/api/ask.py`). The interactive documentation is served at `/docs`.

* The request body is JSON with one field, `question`. It is a POST with a body rather than a GET with a query parameter because questions are free text that may be long and need no URL encoding this way, and because query strings end up in proxy and server access logs while bodies do not. Whitespace around the question is stripped; an empty question or one longer than 2 000 characters is rejected with `422`
* The response is JSON with `result`, the text of the answer, and `sources`, the passages the answer names as its sources, best ranked first, each with `title` (the citation heading), `score` and `source` (the text of the passage)
* A question that cannot be answered, because the chat model, the embedding model or the database fails, is answered with `500` and a generic message; the cause is logged with its traceback but not returned, so that nothing about the internals of the service leaks to the caller. A question that takes longer than `ANSWER_TIMEOUT` seconds in total (120 by default) is cut off and answered with `504`, also with a log entry of its own. The timeout is the only limit on the chat model, which has no timeout of its own
