"""
Memory Service for Aggressive Debator Agent

Manages ChromaDB-based memory for learning from past aggressive risk analyses.
"""

from mem0 import Memory


class MemoryService:
    """Manages memory for the Aggressive Debator agent using ChromaDB."""

    def __init__(self):
        """Initialize the memory service with ChromaDB configuration."""
        # Configuration for Memory
        config = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "neutral_debator_memories",
                    "path": "data/chroma_memories",
                },
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "qwen3:8b",
                    "openai_base_url": "http://localhost:11434/v1",
                    "api_key": "ollama",
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "embeddinggemma:latest",
                    "openai_base_url": "http://localhost:11434/v1",
                    "api_key": "ollama",
                    "embedding_dims": 768,
                },
            },
        }

        # Initialize Memory with the config
        self.memory = Memory.from_config(config_dict=config)
        self.user_id = "neutral_debator_agent"

    def add_memory(self, text: str, metadata: dict = None):
        """
        Add a memory to the vector store.

        Args:
            text: The memory text to store
            metadata: Optional metadata dictionary
        """
        try:
            self.memory.add(
                messages=text,
                user_id=self.user_id,
                metadata=metadata or {},
            )
        except Exception as e:
            print(f"Warning: Failed to add memory: {e}")

    def search_memories(self, query: str, n_results: int = 3):
        """
        Search for relevant memories.

        Args:
            query: Search query
            n_results: Number of results to return

        Returns:
            List of relevant memories
        """
        try:
            results = self.memory.search(
                query=query,
                user_id=self.user_id,
                limit=n_results,
            )
            return results
        except Exception as e:
            print(f"Warning: Failed to search memories: {e}")
            return []

    def get_all_memories(self):
        """
        Get all memories for this agent.

        Returns:
            List of all memories
        """
        try:
            results = self.memory.get_all(user_id=self.user_id)
            return results
        except Exception as e:
            print(f"Warning: Failed to get all memories: {e}")
            return []
