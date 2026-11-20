Actsistant
==========

An assistant for the EU AI Act: ask a compliance question, get an answer that cites the articles it relied on. RAG backend built with FastAPI, LangGraph and Weaviate; runs on a cloud LLM or fully locally with Ollama.

# Prerequisites

* 16 GB of RAM
* [Ollama](https://ollama.com/download)
* [Docker Desktop](https://docs.docker.com/get-docker/desktop/)
* Optional: [VS Code](https://code.visualstudio.com/download) for debugging

# Quick start

* Clone the repo
* Run init.command
  * In case of insufficient priveleges
    * CD into the scripts folder and use `ls -l` to see access priviledges
    * If missing, use `chmod +x init-repo.command` to add execute priviledge
* Run run.command
* Example usage: [localhost:5005/api/ask?query=What is the EU AI Act?](http://localhost:5005/api/ask?query=What is the EU AI Act?)
* Documentation: [localhost:5005/docs](http://localhost:5005/docs)
* To reset everything locally, run cleanup.command

# Debugging

* Open Actsistant.code-workspace in VS Code (double click it)

# Database

On its first startup the app downloads the EU AI Act, chunks it, embeds the chunks with an embedding model served by Ollama and stores chunks and vectors in Weaviate. Later startups skip this because the collection is already populated. `cleanup.command` removes the Weaviate volume and the downloaded Act, so the next startup starts from scratch. Ollama has to be running whenever the app runs: the embedding model is needed to embed each question as well.

* Source: the official XHTML of Regulation (EU) 2024/1689 from the Publications Office (`publications.europa.eu/resource/celex/32024R1689`), kept as `src/database/eu_ai_act.xhtml`
* Chunking follows the structure of the Act: one chunk per recital, per numbered article paragraph (or per article when it has no numbered paragraphs) and per annex. Units longer than ~2 500 characters that consist of a list of points are split into one chunk per point, each prefixed with its lead-in text
* Weaviate collection `EuAiActChunk`, one object per chunk, with the properties `chunk_id` (e.g. `art_6.par_1`), `kind` (recital / article / annex), `heading` (citation, e.g. `Article 6(1)`), `title`, `chapter`, `section`, `article`, `paragraph`, `text` and `position`
* Vectors are computed by the app (the collection is configured for self-provided vectors) with `qwen3-embedding:0.6b`, pulled by `init.command`. The embedded text of a chunk is its heading and title followed by its text. Another Ollama model can be set with the `EMBEDDING_MODEL` environment variable; as vectors of different models cannot be compared, the model is recorded in the collection and a change rebuilds the collection on the next startup
* Retrieval is hybrid search: vector search on the embedded question combined with BM25 keyword search
