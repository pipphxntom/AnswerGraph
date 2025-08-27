from typing import List, Dict, Any, Optional
import time
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from src.core.config import settings


class Retriever:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    
    def embed_query(self, query: str) -> List[float]:
        """Embed the query text."""
        return self.embedding_model.encode(query).tolist()
    
    async def retrieve(
        self, 
        query: str, 
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve documents based on query embedding."""
        start_time = time.time()
        
        # Convert query to embedding
        query_vector = self.embed_query(query)
        
        # Prepare filter if provided
        search_filter = None
        if filters:
            filter_conditions = []
            for field, value in filters.items():
                if isinstance(value, list):
                    # Handle multiple possible values
                    for val in value:
                        filter_conditions.append(
                            FieldCondition(key=field, match=MatchValue(value=val))
                        )
                else:
                    filter_conditions.append(
                        FieldCondition(key=field, match=MatchValue(value=value))
                    )
                    
            if filter_conditions:
                search_filter = Filter(must=filter_conditions)
        
        # Search for similar vectors
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=search_filter
        )
        
        # Process results
        results = []
        for res in search_results:
            # Extract payload and score
            payload = res.payload
            payload["id"] = res.id
            payload["score"] = res.score
            payload["processing_time"] = time.time() - start_time
            results.append(payload)
        
        return results


# Create a singleton instance
retriever = Retriever()


async def retrieve_documents(
    query: str, 
    limit: int = 5,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Retrieve documents based on query."""
    return await retriever.retrieve(query, limit, filters)
