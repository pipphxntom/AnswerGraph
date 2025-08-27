"""
Evaluation script for RAG system using a gold dataset.

This script evaluates the performance of the RAG system against a set of
predefined "gold" queries and expected answers.
"""
import argparse
import asyncio
import csv
import json
import logging
import time
from typing import Dict, List, Any, Tuple, Optional
import numpy as np
from sentence_transformers import SentenceTransformer, util

from src.rag.retriever import retrieve_documents
from src.rag.reranker import rerank_documents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RAGEvaluator:
    """
    Evaluates RAG system performance using various metrics.
    """
    
    def __init__(self, gold_dataset_path: str, embedding_model: Optional[str] = None):
        """
        Initialize the evaluator with a gold dataset.
        
        Args:
            gold_dataset_path: Path to the gold dataset file (CSV or JSON)
            embedding_model: Name of the embedding model for semantic similarity
        """
        self.gold_dataset_path = gold_dataset_path
        self.gold_data = self._load_gold_dataset()
        
        # Initialize embedding model for semantic similarity evaluation
        self.embedding_model_name = embedding_model or "sentence-transformers/all-MiniLM-L6-v2"
        self.embedding_model = SentenceTransformer(self.embedding_model_name)
        
        logger.info(f"Initialized RAG Evaluator with {len(self.gold_data)} gold queries")
    
    def _load_gold_dataset(self) -> List[Dict[str, Any]]:
        """Load the gold dataset from file."""
        extension = self.gold_dataset_path.split('.')[-1].lower()
        
        if extension == 'csv':
            return self._load_from_csv()
        elif extension in ['json', 'jsonl']:
            return self._load_from_json()
        else:
            raise ValueError(f"Unsupported file format: {extension}")
    
    def _load_from_csv(self) -> List[Dict[str, Any]]:
        """Load gold data from CSV file."""
        gold_data = []
        
        with open(self.gold_dataset_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Ensure required fields exist
                if 'query' not in row or 'expected_answer' not in row:
                    logger.warning(f"Skipping row without query or expected_answer: {row}")
                    continue
                
                gold_data.append(row)
        
        return gold_data
    
    def _load_from_json(self) -> List[Dict[str, Any]]:
        """Load gold data from JSON file."""
        with open(self.gold_dataset_path, 'r', encoding='utf-8') as file:
            if self.gold_dataset_path.endswith('.jsonl'):
                # JSONL format (one JSON object per line)
                gold_data = []
                for line in file:
                    if line.strip():
                        gold_data.append(json.loads(line))
            else:
                # Regular JSON (array of objects)
                gold_data = json.load(file)
                
                # Ensure it's a list
                if not isinstance(gold_data, list):
                    raise ValueError("JSON gold dataset must be an array of objects")
        
        # Validate required fields
        valid_data = []
        for item in gold_data:
            if 'query' not in item or 'expected_answer' not in item:
                logger.warning(f"Skipping item without query or expected_answer: {item}")
                continue
            valid_data.append(item)
        
        return valid_data
    
    async def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate the RAG system on the gold dataset.
        
        Returns:
            Dictionary with evaluation metrics
        """
        logger.info("Starting RAG system evaluation")
        start_time = time.time()
        
        results = []
        
        for idx, gold_item in enumerate(self.gold_data):
            query = gold_item['query']
            expected_answer = gold_item['expected_answer']
            
            logger.info(f"Evaluating query {idx+1}/{len(self.gold_data)}: {query}")
            
            # Get system response
            retrieved_docs = await retrieve_documents(
                query=query,
                limit=gold_item.get('top_k', 5)
            )
            
            # Rerank if multiple documents
            if len(retrieved_docs) > 1:
                retrieved_docs = rerank_documents(query, retrieved_docs)
            
            # Extract content from top result
            top_result = retrieved_docs[0]['content'] if retrieved_docs else ""
            
            # Calculate metrics
            metrics = self._calculate_metrics(query, top_result, expected_answer)
            
            # Store result
            result = {
                "query": query,
                "expected_answer": expected_answer,
                "system_answer": top_result,
                "metrics": metrics
            }
            results.append(result)
        
        # Calculate aggregate metrics
        aggregate_metrics = self._calculate_aggregate_metrics(results)
        
        # Prepare final evaluation report
        evaluation_report = {
            "dataset": self.gold_dataset_path,
            "total_queries": len(self.gold_data),
            "aggregate_metrics": aggregate_metrics,
            "individual_results": results,
            "execution_time": time.time() - start_time
        }
        
        logger.info(f"Evaluation complete. Overall semantic similarity: {aggregate_metrics['avg_semantic_similarity']:.4f}")
        return evaluation_report
    
    def _calculate_metrics(
        self, 
        query: str, 
        system_answer: str, 
        expected_answer: str
    ) -> Dict[str, float]:
        """Calculate evaluation metrics for a single query."""
        # Calculate semantic similarity
        semantic_similarity = self._semantic_similarity(system_answer, expected_answer)
        
        # Calculate exact match (if expected answer is found in system answer)
        exact_match = 1.0 if expected_answer.lower() in system_answer.lower() else 0.0
        
        # Calculate token overlap (basic)
        system_tokens = set(system_answer.lower().split())
        expected_tokens = set(expected_answer.lower().split())
        
        if expected_tokens:
            token_overlap = len(system_tokens.intersection(expected_tokens)) / len(expected_tokens)
        else:
            token_overlap = 0.0
        
        return {
            "semantic_similarity": semantic_similarity,
            "exact_match": exact_match,
            "token_overlap": token_overlap
        }
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts."""
        if not text1 or not text2:
            return 0.0
        
        # Embed texts
        embedding1 = self.embedding_model.encode(text1, convert_to_tensor=True)
        embedding2 = self.embedding_model.encode(text2, convert_to_tensor=True)
        
        # Calculate cosine similarity
        similarity = util.pytorch_cos_sim(embedding1, embedding2).item()
        
        return float(similarity)
    
    def _calculate_aggregate_metrics(
        self, 
        results: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate aggregate metrics across all queries."""
        semantic_similarities = [r["metrics"]["semantic_similarity"] for r in results]
        exact_matches = [r["metrics"]["exact_match"] for r in results]
        token_overlaps = [r["metrics"]["token_overlap"] for r in results]
        
        return {
            "avg_semantic_similarity": np.mean(semantic_similarities),
            "avg_exact_match": np.mean(exact_matches),
            "avg_token_overlap": np.mean(token_overlaps)
        }
    
    def save_report(self, report: Dict[str, Any], output_path: str) -> None:
        """Save evaluation report to file."""
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(report, file, indent=2)
        
        logger.info(f"Evaluation report saved to {output_path}")


async def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG system with gold dataset")
    parser.add_argument(
        "--gold-dataset", 
        required=True, 
        help="Path to gold dataset file (CSV or JSON)"
    )
    parser.add_argument(
        "--output", 
        default="eval_results.json", 
        help="Path to save evaluation results"
    )
    parser.add_argument(
        "--embedding-model", 
        default=None, 
        help="Embedding model for semantic similarity"
    )
    
    args = parser.parse_args()
    
    # Initialize evaluator
    evaluator = RAGEvaluator(
        gold_dataset_path=args.gold_dataset,
        embedding_model=args.embedding_model
    )
    
    # Run evaluation
    report = await evaluator.evaluate()
    
    # Save report
    evaluator.save_report(report, args.output)


if __name__ == "__main__":
    asyncio.run(main())
