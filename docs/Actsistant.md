Actsistant
==========

Actsistant is an AI tool that can answer questions on the EU AI Act. 

Currently, the repo is just a quick-and-dirty PoC.

# Architecture

## API

To try out the endpoints: [localhost:5005/docs](http://localhost:5005/docs)

The api uses FastAPI's built-in mechanisms to verify the input.

There are no blocking function calls when running the service in the cloud even though the Weaviate client is synchronous. Data is retrieved from the database using a worker thread.

## Database

The downloaded AI Act is stored in a [Weaviate](https://weaviate.io/) database. Hybrid search is used to find relevant chunks (semantic search + BM25 keyword search).

Reasons for choosing Weaviate:
* Hybrid search in one call
* Weaviate is one of the established vector databases

The act is downloaded, chunked and embeddings are created on the first startup. This takes about a minute on a MacBook Pro.

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

### Chunking

Chunking follows the organic structure of the document: one unit of legal text (e.g. a paragraph) corresponds to one chunk. The heading of the text is stored in the chunk because it's often the heading that specifies what the text applies to.

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

## Agents

The agent implements simple RAG using one tool that does a hybrid search against the Weaviate database.

By default, the Qwen 3 (8B) model is used locally through Ollama.

If you want to use GPT-6 Luna instead, add a .env file with an OpenAI API key:

```
OPENAI_API_KEY="..."
LOCAL_RUN_ONLY=False
```

If you want to revert back to using the local model, set the `LOCAL_RUN_ONLY` variable to True.

## Scripts

The repo comes with scripts that prepare everyhing that is needed to run the service locally if the necessary software and hardware requirements are met. There is also a cleanup script that resets everything.

# Metrics

The most important metrics of the application:
* Response accuracy
* Response latency
* Average tokens per request
* Average cost per request
* Total and average number of users broken down hourly/daily/weekly/monthly

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

* Refactor the entire repo to turn the current "quick-and-dirty" solution production-ready
* Start improving accuracy interatively by fine-tuning the chunking, the embedding, the search (semantic vs. BM25), and the agentic workflow (e.g. adding a rephraser agent, improving the prompts or trying different models)
* Integrate cloud solution for the embedding model
