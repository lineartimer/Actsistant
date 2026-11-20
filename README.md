Actsistant
==========

An assistant for the EU AI Act: ask a compliance question, get an answer that cites the articles it relied on. RAG backend built with FastAPI, LangGraph and Weaviate; runs on a cloud LLM or fully locally with Ollama.

# Prerequisites

* 16 GB of RAM
* [Ollama](https://ollama.com/download)
* [Docker Desktop](https://docs.docker.com/get-docker/desktop/)

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