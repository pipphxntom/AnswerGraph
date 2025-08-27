#!/usr/bin/env python
"""
PDF Processing Performance Benchmark

This script evaluates the performance of our PDF processing pipeline
with various configurations and document types.

Usage:
    python benchmark_pdf_processing.py --directory /path/to/pdfs --runs 3

Results will be saved to a CSV file and visualized as graphs.
"""
import os
import sys
import time
import argparse
import asyncio
import logging
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import processing modules
from src.ingest.pdf.enhanced_processor import EnhancedPDFProcessor, ProcessingConfig
from src.ingest.pdf.policy_processor import create_policy_from_pdf as legacy_processor
from src.ingest.pdf.extractor import process_pdf as legacy_extractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Test configurations
TEST_CONFIGS = [
    # Format: (name, processor_type, config_dict)
    ("legacy-200-400", "legacy", {"min_tokens": 200, "max_tokens": 400}),
    ("legacy-100-300", "legacy", {"min_tokens": 100, "max_tokens": 300}),
    ("enhanced-semantic", "enhanced", {
        "min_tokens": 200, 
        "max_tokens": 400,
        "chunk_strategy": "semantic"
    }),
    ("enhanced-fixed", "enhanced", {
        "min_tokens": 200, 
        "max_tokens": 400,
        "chunk_strategy": "fixed"
    }),
    ("enhanced-optimized", "enhanced", {
        "min_tokens": 200, 
        "max_tokens": 400,
        "chunk_strategy": "semantic",
        "max_workers": 8,
        "batch_size": 20
    }),
]

class PDFBenchmark:
    """Benchmark different PDF processing configurations."""
    
    def __init__(self, pdf_directory: str, output_dir: str = "benchmark_results"):
        """Initialize benchmark with PDF directory."""
        self.pdf_directory = Path(pdf_directory)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Find PDF files
        self.pdf_files = list(self.pdf_directory.glob("**/*.pdf"))
        if not self.pdf_files:
            raise ValueError(f"No PDF files found in {pdf_directory}")
        
        logger.info(f"Found {len(self.pdf_files)} PDF files for benchmarking")
        
        # Results dataframe
        self.results = []
    
    async def run_benchmark(self, runs: int = 3):
        """Run benchmark with multiple configurations and runs."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        for pdf_file in self.pdf_files:
            logger.info(f"Benchmarking file: {pdf_file.name}")
            
            # Get file metadata
            file_size_mb = pdf_file.stat().st_size / (1024 * 1024)
            
            for config_name, processor_type, config in TEST_CONFIGS:
                logger.info(f"Testing configuration: {config_name}")
                
                for run in range(1, runs + 1):
                    logger.info(f"Run {run}/{runs}")
                    
                    # Run benchmark for this configuration
                    start_time = time.time()
                    memory_before = self._get_memory_usage()
                    
                    try:
                        if processor_type == "legacy":
                            # Legacy processor
                            chunks = legacy_extractor(
                                str(pdf_file),
                                min_tokens=config["min_tokens"],
                                max_tokens=config["max_tokens"]
                            )
                            chunk_count = len(chunks)
                            token_count = sum(len(c.get("text", "")) for c in chunks) // 4  # Rough estimate
                        else:
                            # Enhanced processor
                            processor_config = ProcessingConfig(
                                min_tokens=config["min_tokens"],
                                max_tokens=config["max_tokens"],
                                chunk_strategy=config.get("chunk_strategy", "semantic"),
                                max_workers=config.get("max_workers", 4),
                                batch_size=config.get("batch_size", 10)
                            )
                            processor = EnhancedPDFProcessor(processor_config)
                            result = await processor.process_pdf(str(pdf_file))
                            chunk_count = len(result["chunks"])
                            token_count = result["stats"]["total_tokens"]
                        
                        elapsed_time = time.time() - start_time
                        memory_after = self._get_memory_usage()
                        memory_used = memory_after - memory_before
                        
                        # Record results
                        self.results.append({
                            "file": pdf_file.name,
                            "file_size_mb": file_size_mb,
                            "config": config_name,
                            "run": run,
                            "elapsed_time": elapsed_time,
                            "memory_mb": memory_used,
                            "chunk_count": chunk_count,
                            "token_count": token_count,
                            "chunks_per_second": chunk_count / elapsed_time if elapsed_time > 0 else 0,
                            "tokens_per_second": token_count / elapsed_time if elapsed_time > 0 else 0,
                            "success": True
                        })
                    
                    except Exception as e:
                        logger.error(f"Error benchmarking {pdf_file.name} with {config_name}: {str(e)}")
                        
                        # Record failure
                        self.results.append({
                            "file": pdf_file.name,
                            "file_size_mb": file_size_mb,
                            "config": config_name,
                            "run": run,
                            "elapsed_time": time.time() - start_time,
                            "memory_mb": 0,
                            "chunk_count": 0,
                            "token_count": 0,
                            "chunks_per_second": 0,
                            "tokens_per_second": 0,
                            "success": False
                        })
        
        # Convert results to DataFrame
        df = pd.DataFrame(self.results)
        
        # Save results
        csv_path = self.output_dir / f"benchmark_results_{timestamp}.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved benchmark results to {csv_path}")
        
        # Generate visualizations
        self._create_visualizations(df, timestamp)
        
        return df
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    
    def _create_visualizations(self, df: pd.DataFrame, timestamp: str):
        """Create visualization of benchmark results."""
        # Set style
        sns.set(style="whitegrid")
        plt.figure(figsize=(12, 10))
        
        # Filter successful runs
        success_df = df[df["success"] == True].copy()
        
        # Calculate average per configuration and file
        avg_df = success_df.groupby(["file", "config"]).agg({
            "elapsed_time": "mean",
            "memory_mb": "mean",
            "chunk_count": "mean",
            "chunks_per_second": "mean",
            "tokens_per_second": "mean"
        }).reset_index()
        
        # Plot 1: Processing time by configuration
        plt.subplot(2, 2, 1)
        sns.barplot(x="config", y="elapsed_time", data=avg_df)
        plt.title("Average Processing Time by Configuration")
        plt.xlabel("Configuration")
        plt.ylabel("Time (seconds)")
        plt.xticks(rotation=45)
        
        # Plot 2: Memory usage by configuration
        plt.subplot(2, 2, 2)
        sns.barplot(x="config", y="memory_mb", data=avg_df)
        plt.title("Average Memory Usage by Configuration")
        plt.xlabel("Configuration")
        plt.ylabel("Memory (MB)")
        plt.xticks(rotation=45)
        
        # Plot 3: Chunks per second by configuration
        plt.subplot(2, 2, 3)
        sns.barplot(x="config", y="chunks_per_second", data=avg_df)
        plt.title("Chunks Processed per Second")
        plt.xlabel("Configuration")
        plt.ylabel("Chunks/second")
        plt.xticks(rotation=45)
        
        # Plot 4: Tokens per second by configuration
        plt.subplot(2, 2, 4)
        sns.barplot(x="config", y="tokens_per_second", data=avg_df)
        plt.title("Tokens Processed per Second")
        plt.xlabel("Configuration")
        plt.ylabel("Tokens/second")
        plt.xticks(rotation=45)
        
        # Adjust layout and save
        plt.tight_layout()
        plt.savefig(self.output_dir / f"benchmark_summary_{timestamp}.png")
        
        # Create additional plots for detailed analysis
        plt.figure(figsize=(14, 8))
        
        # Plot 5: Processing time vs file size by configuration
        sns.scatterplot(
            x="file_size_mb", 
            y="elapsed_time", 
            hue="config", 
            style="config",
            s=100,
            data=avg_df
        )
        plt.title("Processing Time vs File Size")
        plt.xlabel("File Size (MB)")
        plt.ylabel("Time (seconds)")
        plt.grid(True)
        
        # Add trend lines
        for config in avg_df["config"].unique():
            config_df = avg_df[avg_df["config"] == config]
            if len(config_df) > 1:
                x = config_df["file_size_mb"]
                y = config_df["elapsed_time"]
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                plt.plot(x, p(x), linestyle="--")
        
        plt.savefig(self.output_dir / f"benchmark_scaling_{timestamp}.png")
        
        logger.info(f"Saved visualizations to {self.output_dir}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Benchmark PDF processing")
    parser.add_argument("--directory", "-d", required=True, help="Directory containing PDF files")
    parser.add_argument("--output", "-o", default="benchmark_results", help="Output directory for results")
    parser.add_argument("--runs", "-r", type=int, default=3, help="Number of runs per configuration")
    
    args = parser.parse_args()
    
    benchmark = PDFBenchmark(args.directory, args.output)
    await benchmark.run_benchmark(runs=args.runs)
    
    logger.info("Benchmark complete")


if __name__ == "__main__":
    asyncio.run(main())
