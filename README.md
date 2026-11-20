Actsistant
==========

An assistant for the EU AI Act: ask a compliance question, get an answer that cites the articles it relied on. RAG backend built with FastAPI, LangGraph and Weaviate; runs on a cloud LLM or fully locally with Ollama.

# Quick start

* Run init.command
  * In case of insufficient priveleges
    * Cd into the scripts folder and use `ls -l` to see access priviledges
    * Use `chmod +x init-repo.command` to add execute priviledge
* Start Docker Desktop
* Open a terminal in VS Code and run:
* Run `docker compose up -d weaviate`
* To ask Actsistant a question: [localhost:5005/api/ask?query=What is the EU AI Act?](http://localhost:5005/api/ask?query=What is the EU AI Act?)
* Documentation: [localhost:5005/docs](http://localhost:5005/docs)
* To reset everything locally, run cleanup.command