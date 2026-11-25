Actsistant
==========

Actsistant is an AI assistant backend built with FastAPI, LangGraph and Weaviate that answers compliance questions about the EU AI Act. The answers include sources if the question can be answered based on the legal text.

Typical users that can benefit from using Actsistant:
* Product owners or engineering teams that build agentic AI systems
* An internal compliance team approving the company's AI tools
* Consultants on AI governance

The service can be run using a cloud LLM or fully locally with Ollama.

Currently, the repo is just a PoC.

The EU AI Act is available as a pdf [here](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689).

# Prerequisites

* [Docker Desktop](https://docs.docker.com/get-docker/desktop/)
* Optional: [VS Code](https://code.visualstudio.com/download) for debugging

# Quickstart

* Clone the repo and start Docker Desktop
* Open a terminal, CD into the `src` folder and run `docker compose up --build -d --wait`
* The first startup will take longer because both the embedding model and the language model for local run need to be downloaded, the EU AI Act needs to be chunked, and the embeddings must be created. Also, when run in a container, Ollama has no access to the GPU
* Once the above command returns (which takes altogether about 24 mins on a 2022 MacBook Pro), open [localhost:5005/docs](http://localhost:5005/docs) in a browser
* Click the "Try it out" button under the ask endpoint, and supply a question or use one of the questions that are provided with the documentation:
  * Can my employer use AI to read my emotions at work?
  * Is AI that screens job applications considered high-risk?
  * Has any company been fined under the AI Act yet?
* The first two of these questions can be answered using the text, the third one cannot

## Configuring model usage (local vs. cloud)

* Rename .env.example to .env
* With no API key, the local Qwen 3 (8B) model will be used
* If you want to use the GPT 6 Luna model for question answering, insert your own OpenAI API key
* If you want to revert to the Qwen 3 (8B) model again, change the `LOCAL_RUN_ONLY` variable to `True`
* After changing the .env file, CD into the `src` folder, and run `docker compose up -d --wait`
* If the local model hasn't been downloaded, this change will take some time (about 10 mins on a MacBook Pro) but it only has to be done once. For each subsequent changes, it will take only a few seconds for the model change to take effect

# Debugging

* Open Actsistant.code-workspace in VS Code (double-click it)
* Open a terminal and CD into the `src` folder
* Run the following commands (note that you might need python/pip instead of python3/pip3)
  * `python3 -m venv .venv`
  * `source .venv/bin/activate`
  * `pip3 install --upgrade pip`
  * `pip3 install -r requirements.txt`
* Hit F5 and open [localhost:5006/docs](http://localhost:5006/docs)

# Testing

Prerequisites:
* Virtual environment with dependencies in place (see Debugging)

In VS Code, click on the test tab and run the tests.

Alternatively, run tests from the terminal:
* Open a terminal, and CD into the `src` folder
* Run `source .venv/bin/activate`
* Run `pytest`

# More information

A detailed documentation of Actsistant can be found in the `docs` folder.
