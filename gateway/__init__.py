"""gateway module — OpenHTTP AI Agent Gateway 

Core modules:
  server.py    → GatewayServer (OpenAI-compatible API + session management)
  router.py    → WorkerRouter (py_workers + legacy worker routing)
  workspace.py → StructuredWorkspace (O(1) context via structured slots)
  rag.py       → HybridRAG (BM25 + Semantic retrieval augmentation)
  inference.py → InferenceDispatcher (L1/L2/L3 task-graded model selection)
  runner.py    → CLI entry + signal handling + graceful shutdown
"""
from gateway.runner import run_gateway
from gateway.server import GatewayServer, start_gateway

__all__ = ["run_gateway", "GatewayServer", "start_gateway"]
