Actsistant
==========

Actsistant is an AI tool that can answer questions on the EU AI Act. 

Currently, the repo is in a PoC stage.

# Architecture

## API

The api is built with FastAPI and it uses the mechanisms that FastAPI provides to verify the input (e.g. length the input question).

There are no blocking function calls when running the service in the cloud even though the Weaviate client is synchronous. Data is retrieved from the database using a worker thread.

There is a standard `/health` endpoint implemented.

## Database

The downloaded AI Act is stored in a [Weaviate](https://weaviate.io/) database. Hybrid search is used to find relevant chunks (semantic search + BM25 keyword search).

Reasons for choosing Weaviate:
* Hybrid search in one call
* Weaviate is one of the established vector databases

On the first startup, the act is downloaded, chunked and embeddings are created.

The Weaviate collection has the following properties:
* `chunk_id`
* `kind`
* `heading`
* `title`
* `chapter`
* `section`
* `article`
* `paragraph`
* `text`
* `position`

The contents of the database can be viewed with Weaviate Studio (a VS Code extension).

### Chunking

Chunking follows the organic structure of the document: one unit of legal text (e.g. a paragraph) corresponds to one chunk. The heading of the text is stored in the chunk because it's often the heading that specifies what the text applies to.

With this design, there is no need for overlapping chunks, and one citation in the response will correspond to one unit of text in the act.

The downside is that chunk sizes vary, and for long chunks, the quality of the search might decrease. No chunk gets truncated.

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

## Agents

The agent implements simple RAG using one tool that does a hybrid search against the Weaviate database.

By default, the Qwen 3 (8B) model is used locally through Ollama.

If you want to use the GPT-6 Luna model instead, add an OpenAI API key to the .env file:

```
OPENAI_API_KEY="..."
LOCAL_RUN_ONLY=False
```

If you want to revert back to using the local model, set the `LOCAL_RUN_ONLY` variable to True.

The models used can be configured in `config.py` (see variables `EMBEDDING_MODEL`, `LOCAL_CHAT_MODEL`, `CLOUD_CHAT_MODEL`)

## Scripts

The repo comes with a cleanup script (untested for Windows) that deletes temporary files from the local copy of the repo.

# Metrics

Currently, no metrics are being collected. In order to start improving the question answering capbility of this service, metrics will be needed. The most important/useful metrics are:
* Response accuracy
* Response latency
* Average tokens per request
* Average cost per request
* Total and average number of users broken down hourly/daily/weekly/monthly

There is one test that measures the accuracy of the search on a golden dataset, and it is about 85% right now. The golden dataset was generated with Fable 5.1 with reasoning set to "extra high".

# Limitations

* History not being kept
* No user management/authentication implemented
* The codebase can only run with an embedding model running locally in Ollama

# Tests

As this is just a PoC, the tool isn't being extensively tested.

Currently, there are tests for the following:
* Content of the database
* The search
* HTTP behavior of the API

# Next steps

* Refactor the entire repo to turn the current PoC-stage solution production-ready
* Start improving accuracy interatively by fine-tuning the chunking, the embedding, the search (semantic vs. BM25), and the agentic workflow (e.g. adding a rephraser agent, or improving the prompts, or trying different models)
* Integrate cloud solution for the embedding model
