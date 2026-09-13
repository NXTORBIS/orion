"""The ORION system layer (project brief §3, §10–14, §22–23, §32):

    USER -> API -> ORCHESTRATOR -> [MEMORY | RAG | TOOLS] -> MODEL ROUTER -> backends
         -> VERIFIER -> RESPONSE ENGINE -> USER

* ``backends``        — model backends (local transformers model, llama.cpp server)
* ``tools``           — tool registry, structured tool calls, execution
* ``rag``             — chunking, BM25 + optional dense retrieval, fusion, reranking, citations
* ``memory``          — short-term / long-term (user-approved) / semantic / working memory
* ``router``          — query analysis and expert selection
* ``response_engine`` — generate -> verify -> improve -> finalize over candidates
* ``orchestrator``    — plan -> retrieve -> act with tools -> generate -> verify -> correct -> answer
"""
