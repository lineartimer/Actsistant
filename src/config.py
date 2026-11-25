import os


LOCAL_RUN_ONLY = os.getenv("LOCAL_RUN_ONLY", "False").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

API_PORT = int(os.getenv("API_PORT", "5005"))

WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "localhost")
WEAVIATE_PORT = int(os.getenv("WEAVIATE_PORT", "8080"))
WEAVIATE_GRPC_PORT = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:0.6b")

LOCAL_CHAT_MODEL = os.getenv("LOCAL_CHAT_MODEL", "qwen3:8b")
CLOUD_CHAT_MODEL = os.getenv("CLOUD_CHAT_MODEL", "gpt-6-luna")

ANSWER_TIMEOUT = float(os.getenv("ANSWER_TIMEOUT", "120"))
