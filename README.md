Actsistant
==========

Actsistant is an AI assistant backend built with FastAPI, LangGraph and Weaviate that answers compliance questions about the EU AI Act. The answers contain sources if the question can be answered based on the legal text.

Typical users that can benefit from using Actsistant:
* Product owners or engineering teams that build agentic AI systems
* An internal compliance team approving the company's AI tools
* Consultants on AI governance

The service can be run using a cloud LLM or fully locally with Ollama.

The EU AI Act is available as a pdf [here](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689).

# Prerequisites

* [Docker Desktop](https://docs.docker.com/get-docker/desktop/)
* Optional: [VS Code](https://code.visualstudio.com/download) for debugging

For local run:
* 16 GB of RAM
* [Ollama](https://ollama.com/download)

# Quickstart

Clone the repo and start Docker Desktop.

The first startup will take longer because the EU AI Act must be downloaded, chunked, and the embeddings must be created.

Depending on your system, follow the below instructions:

Windows

* Run `scripts\win\init.ps1`
* Run `scripts\win\run.ps1`
* Open [http://localhost:5005/docs](http://localhost:5005/docs) and have a play with the endpoints
* To reset everything locally, run the cleanup script: `scripts\win\cleanup.ps1`

MacOS

* Run `scripts/mac/init.command`
  * In case of insufficient privileges, cd into `scripts/mac` and use `ls -l` to see access privileges
  * If missing, use `chmod +x *.command` to add execute privilege
* Run `scripts/mac/run.command`
* Open [http://localhost:5005/docs](http://localhost:5005/docs) and have a play with the endpoints
* To reset everything locally, run the cleanup script: `scripts/mac/cleanup.command`

Example questions

* Is AI that screens job applications considered high-risk?
* Can my employer use AI to read my emotions at work?
* Has any company been fined under the AI Act yet?

The first two of these questions can be answered using the text, the third one cannot.

# Debugging

* Open Actsistant.code-workspace in VS Code (double-click it)
* Hit F5

# Testing

Prerequisites:
* The init script has been run
* The application has been started at least once

In VS Code, click on the test tab and run the tests.

Alternatively, run tests from the terminal:
* CD into the `src` folder
* Rune `source .venv/bin/activate`
* Run `pytest`

# More information

A detailed documentation of Actsistant can be found in the `docs` folder.
