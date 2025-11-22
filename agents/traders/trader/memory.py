from mem0 import Memory


class MemoryService:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        config = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "agent_memories",
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
        self.initialize_memory(config)

    def initialize_memory(self, config: dict):
        self.memory = Memory.from_config(config)

    def add_memory(self, memory, ticker: str):
        self.memory.add(memory, user_id=ticker, agent_id=self.agent_id, infer=True)

    def get_memories(self):
        return self.memory.get_all(agent_id=self.agent_id)

    def search_memories(self, current_situation: str, ticker: str, n_matches: int = 2):
        return self.memory.search(
            current_situation, user_id=ticker, agent_id=self.agent_id, limit=n_matches
        )


if __name__ == "__main__":
    m = MemoryService(agent_id="trader")
    # Add a memory
    messages = [
        {
            "role": "system",
            "content": "You are a trader executing investment decisions.",
        },
        {
            "role": "user",
            "content": "Should I execute this buy order?",
        },
        {
            "role": "assistant",
            "content": "Yes, executed BUY order for 100 shares. The fundamentals and technical indicators align with the investment plan.",
        },
    ]

    result = m.add_memory(messages)
    print("Add memory result:", result)

    # Retrieve memories
    memories = m.get_memories()
    print("Memories for agent 'trader':", memories)
