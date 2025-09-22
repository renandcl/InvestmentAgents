from mem0 import Memory


class MemoryService:
    def __init__(self, user_id: str):
        self.user_id = user_id
        config = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "agent_memories",
                    "path": "data/chroma_memories",
                },
            },
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": "llama3.1:latest",
                    "ollama_base_url": "http://localhost:11434",
                },
            },
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": "nomic-embed-text",
                    "ollama_base_url": "http://localhost:11434",
                    "embedding_dims": 768,
                },
            },
        }
        self.initialize_memory(config)

    def initialize_memory(self, config: dict):
        self.memory = Memory.from_config(config)

    def add_memory(self, memory):
        self.memory.add(memory, user_id=self.user_id, infer=False)

    def get_memories(self):
        return self.memory.get_all(user_id=self.user_id)


if __name__ == "__main__":
    m = MemoryService(user_id="test_user_id")
    # Add a memory
    messages = [
        {
            "role": "user",
            "content": "I'm planning to watch a movie tonight. Any recommendations?",
        },
        {
            "role": "assistant",
            "content": "How about a thriller movies? They can be quite engaging.",
        },
        {
            "role": "user",
            "content": "I'm not a big fan of thriller movies but I love sci-fi movies.",
        },
        {
            "role": "assistant",
            "content": "Got it! I'll avoid thriller recommendations and suggest sci-fi movies in the future.",
        },
    ]

    result = m.memory.add(messages, user_id="test_user_id", infer=False)
    print("Add memory result:", result)

    # Retrieve memories
    memories = m.memory.get_all(user_id="test_user_id")
    print("Memories for user 'test_user_id':", memories)
