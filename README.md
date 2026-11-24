Actsistant
==========

Actsistant is an AI assistant backend built with FastAPI, LangGraph and Weaviate that answers compliance questions about the EU AI Act. The answers contain sources if the question can be answered based on the legal text.

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
* Once this command returns (which takes about 12 mins on a 2022 MacBook Pro), open [http://localhost:5005/docs](http://localhost:5005/docs) in the browser
* The first startup will take longer because the EU AI Act must be downloaded, chunked, and the embeddings must be created. When run in a container, Ollama has no access to the GPUs

Example questions

* Can my employer use AI to read my emotions at work?
* Is AI that screens job applications considered high-risk?
* Has any company been fined under the AI Act yet?

The first two of these questions can be answered using the text, the third one cannot.

# Debugging

* Open Actsistant.code-workspace in VS Code (double-click it)
* Open a terminal and CD into the `src` folder
* Run the following commands
  * `python3 -m venv .venv`
  * `source .venv/bin/activate`
  * `pip3 install --upgrade pip`
  * `pip3 install -r requirements.txt`
* Hit F5

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
