"""
Investment Manager Memory Service

Manages persistent memory for workflow orchestration.
"""

import logging
from typing import List

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Memory service for Investment Manager.
    
    Stores:
    - Past workflow executions
    - Successful decision patterns
    - Failed decision patterns
    - Performance metrics
    """

    def __init__(
        self,
        agent_id: str,
        persist_directory: str = "data/chroma_memories",
        embedding_model: str = "nomic-embed-text",
    ):
        self.agent_id = agent_id
        self.collection_name = f"{agent_id}_memories"

        # Initialize ChromaDB client
        self.client = chromadb.Client(
            Settings(
                persist_directory=persist_directory,
                anonymized_telemetry=False,
            )
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"agent_id": agent_id, "hnsw:space": "cosine"},
        )

        logger.info(
            f"Memory service initialized for {agent_id} with collection {self.collection_name}"
        )

    def add_workflow_memory(
        self,
        ticker: str,
        date: str,
        execution_action: str,
        execution_status: str,
        final_decision: str,
        metadata: dict = None,
    ) -> str:
        """
        Store a completed workflow execution in memory.
        
        Args:
            ticker: Stock ticker
            date: Execution date
            execution_action: BUY/SELL/HOLD
            execution_status: APPROVED/HOLD/REJECTED
            final_decision: Final decision text
            metadata: Additional metadata
            
        Returns:
            Memory ID
        """
        try:
            memory_text = f"""
            Workflow Execution: {ticker} on {date}
            Action: {execution_action}
            Status: {execution_status}
            Decision: {final_decision}
            """

            memory_id = f"{ticker}_{date}_{execution_action}"

            memory_metadata = {
                "ticker": ticker,
                "date": date,
                "execution_action": execution_action,
                "execution_status": execution_status,
                "type": "workflow_execution",
            }

            if metadata:
                memory_metadata.update(metadata)

            self.collection.add(
                documents=[memory_text],
                ids=[memory_id],
                metadatas=[memory_metadata],
            )

            logger.info(f"Stored workflow memory: {memory_id}")
            return memory_id

        except Exception as e:
            logger.error(f"Error storing workflow memory: {e}")
            return ""

    def search_similar_workflows(
        self, ticker: str = None, query: str = None, n_results: int = 5
    ) -> List[dict]:
        """
        Search for similar past workflow executions.
        
        Args:
            ticker: Filter by ticker (optional)
            query: Search query text
            n_results: Number of results to return
            
        Returns:
            List of similar workflow memories
        """
        try:
            if not query and ticker:
                query = f"Workflow execution for {ticker}"
            elif not query:
                query = "Past workflow executions"

            where_filter = {"type": "workflow_execution"}
            if ticker:
                where_filter["ticker"] = ticker

            results = self.collection.query(
                query_texts=[query],
                where=where_filter,
                n_results=n_results,
            )

            memories = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    memory = {
                        "text": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0.0,
                    }
                    memories.append(memory)

            logger.info(f"Found {len(memories)} similar workflows")
            return memories

        except Exception as e:
            logger.error(f"Error searching workflows: {e}")
            return []

    def get_workflow_statistics(self) -> dict:
        """
        Get statistics on past workflow executions.
        
        Returns:
            Dictionary with workflow statistics
        """
        try:
            all_results = self.collection.get()

            total_workflows = len(all_results["ids"]) if all_results["ids"] else 0

            if total_workflows == 0:
                return {
                    "total_workflows": 0,
                    "by_action": {},
                    "by_status": {},
                }

            # Count by action
            by_action = {}
            by_status = {}

            if all_results["metadatas"]:
                for metadata in all_results["metadatas"]:
                    action = metadata.get("execution_action", "UNKNOWN")
                    status = metadata.get("execution_status", "UNKNOWN")

                    by_action[action] = by_action.get(action, 0) + 1
                    by_status[status] = by_status.get(status, 0) + 1

            return {
                "total_workflows": total_workflows,
                "by_action": by_action,
                "by_status": by_status,
            }

        except Exception as e:
            logger.error(f"Error getting workflow statistics: {e}")
            return {"total_workflows": 0, "by_action": {}, "by_status": {}}
