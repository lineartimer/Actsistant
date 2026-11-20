Actsistant
==========

An assistant for the EU AI Act: ask a compliance question, get an answer that cites the articles it relied on. RAG backend built with FastAPI, LangGraph and Weaviate; runs on a cloud LLM or fully locally with Ollama.

# Quick start

* Run init-repo.command
  * In case of insufficient priveleges
    * Cd into the scripts folder and use `ls -l` to see access priviledges
    * Use `chmod +x init-repo.command` to add execute priviledge
* Start Docker Desktop
* Open a terminal in VS Code and run:
* Run `docker compose up -d weaviate`