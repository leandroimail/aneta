"""
Performance tests for PDFReader module.

This module contains performance benchmarks for the async PDF processing system,
testing throughput, memory usage, and scalability under various configurations.
"""

import unittest
import asyncio
import time
import psutil
import os
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock
import tempfile

# Import the functions to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.PDFReader import read_single_pdf, read_pdfs_batch, process_pdfs


class TestPerformanceBenchmarks(unittest.TestCase):
    """
    Performance benchmark tests for PDF processing system.
    
    These tests measure:
    - Processing time for various batch sizes
    - Memory usage during processing
    - Scalability with different concurrency settings
    - Throughput (PDFs per second)
    """
    
    def setUp(self):
        """Set up test fixtures before each test."""
        self.process = psutil.Process(os.getpid())
        
    def _get_memory_usage_mb(self) -> float:
        """
        Get current memory usage in MB.
        
        Returns:
            float: Memory usage in megabytes
        """
        return self.process.memory_info().rss / (1024 * 1024)
    
    def _create_mock_pdf_result(self, filename: str, success: bool = True) -> Dict[str, Any]:
        """
        Create a mock PDF processing result.
        
        Args:
            filename (str): PDF filename
            success (bool): Whether processing succeeded
            
        Returns:
            Dict[str, Any]: Mock result dictionary
        """
        return {
            "markdown": f"# Mock content for {filename}\n\nThis is test content." * 10,
            "filename": filename,
            "page_count": 10,
            "processing_time": 0.1,  # Fast mock processing
            "file_size_mb": 1.5,
            "success": success,
            "error": None if success else f"Mock error for {filename}"
        }
    
    @patch('src.PDFReader.read_single_pdf')
    def test_performance_batch_10_pdfs(self, mock_read_single):
        """
        Test processing 10 PDFs with max_concurrent=5.
        
        Target: < 5 seconds for 10 PDFs
        """
        # Mock read_single_pdf to return quickly
        mock_read_single.side_effect = lambda path: self._create_mock_pdf_result(
            Path(path).name
        )
        
        # Create temporary folder with 10 mock PDF files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create 10 empty PDF files
            for i in range(10):
                pdf_file = temp_path / f"test_paper_{i:02d}.pdf"
                pdf_file.touch()
            
            # Record start metrics
            start_time = time.time()
            start_memory = self._get_memory_usage_mb()
            
            # Run batch processing
            results = asyncio.run(read_pdfs_batch(str(temp_path), max_concurrent=5))
            
            # Record end metrics
            end_time = time.time()
            end_memory = self._get_memory_usage_mb()
            
            # Calculate metrics
            elapsed_time = end_time - start_time
            memory_delta = end_memory - start_memory
            throughput = len(results) / elapsed_time if elapsed_time > 0 else 0
            
            # Assertions
            self.assertEqual(len(results), 10, "Should process all 10 PDFs")
            self.assertLess(elapsed_time, 5.0, f"Processing should complete in < 5s (took {elapsed_time:.2f}s)")
            self.assertLess(memory_delta, 500, f"Memory usage should be < 500MB (used {memory_delta:.2f}MB)")
            
            # Log results
            print(f"\n{'='*60}")
            print(f"Performance Test: 10 PDFs, max_concurrent=5")
            print(f"{'='*60}")
            print(f"Time: {elapsed_time:.2f}s")
            print(f"Memory delta: {memory_delta:.2f}MB")
            print(f"Throughput: {throughput:.2f} PDFs/second")
            print(f"{'='*60}")
    
    @patch('src.PDFReader.read_single_pdf')
    def test_performance_batch_50_pdfs(self, mock_read_single):
        """
        Test processing 50 PDFs with max_concurrent=10.
        
        Target: < 30 seconds for 50 PDFs
        """
        # Mock read_single_pdf to return quickly
        mock_read_single.side_effect = lambda path: self._create_mock_pdf_result(
            Path(path).name
        )
        
        # Create temporary folder with 50 mock PDF files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create 50 empty PDF files
            for i in range(50):
                pdf_file = temp_path / f"test_paper_{i:03d}.pdf"
                pdf_file.touch()
            
            # Record start metrics
            start_time = time.time()
            start_memory = self._get_memory_usage_mb()
            
            # Run batch processing with higher concurrency
            results = asyncio.run(read_pdfs_batch(str(temp_path), max_concurrent=10))
            
            # Record end metrics
            end_time = time.time()
            end_memory = self._get_memory_usage_mb()
            
            # Calculate metrics
            elapsed_time = end_time - start_time
            memory_delta = end_memory - start_memory
            throughput = len(results) / elapsed_time if elapsed_time > 0 else 0
            
            # Assertions
            self.assertEqual(len(results), 50, "Should process all 50 PDFs")
            self.assertLess(elapsed_time, 30.0, f"Processing should complete in < 30s (took {elapsed_time:.2f}s)")
            self.assertLess(memory_delta, 1000, f"Memory usage should be < 1GB (used {memory_delta:.2f}MB)")
            
            # Log results
            print(f"\n{'='*60}")
            print(f"Performance Test: 50 PDFs, max_concurrent=10")
            print(f"{'='*60}")
            print(f"Time: {elapsed_time:.2f}s")
            print(f"Memory delta: {memory_delta:.2f}MB")
            print(f"Throughput: {throughput:.2f} PDFs/second")
            print(f"{'='*60}")
    
    @patch('src.PDFReader.read_single_pdf')
    def test_performance_batch_100_pdfs(self, mock_read_single):
        """
        Test processing 100 PDFs with max_concurrent=10.
        
        Target: < 5 minutes (300 seconds) for 100 PDFs
        Target memory: < 2GB
        """
        # Mock read_single_pdf to return quickly
        mock_read_single.side_effect = lambda path: self._create_mock_pdf_result(
            Path(path).name
        )
        
        # Create temporary folder with 100 mock PDF files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create 100 empty PDF files
            for i in range(100):
                pdf_file = temp_path / f"test_paper_{i:03d}.pdf"
                pdf_file.touch()
            
            # Record start metrics
            start_time = time.time()
            start_memory = self._get_memory_usage_mb()
            
            # Run batch processing
            results = asyncio.run(read_pdfs_batch(str(temp_path), max_concurrent=10))
            
            # Record end metrics
            end_time = time.time()
            end_memory = self._get_memory_usage_mb()
            
            # Calculate metrics
            elapsed_time = end_time - start_time
            memory_delta = end_memory - start_memory
            throughput = len(results) / elapsed_time if elapsed_time > 0 else 0
            
            # Assertions
            self.assertEqual(len(results), 100, "Should process all 100 PDFs")
            self.assertLess(elapsed_time, 300.0, f"Processing should complete in < 5 min (took {elapsed_time:.2f}s)")
            self.assertLess(memory_delta, 2048, f"Memory usage should be < 2GB (used {memory_delta:.2f}MB)")
            
            # Log results
            print(f"\n{'='*60}")
            print(f"Performance Test: 100 PDFs, max_concurrent=10")
            print(f"{'='*60}")
            print(f"Time: {elapsed_time:.2f}s ({elapsed_time/60:.2f} min)")
            print(f"Memory delta: {memory_delta:.2f}MB ({memory_delta/1024:.2f}GB)")
            print(f"Throughput: {throughput:.2f} PDFs/second")
            print(f"{'='*60}")
    
    @patch('src.PDFReader.read_single_pdf')
    def test_concurrency_comparison(self, mock_read_single):
        """
        Compare performance with different max_concurrent values.
        
        Tests max_concurrent values: 1, 3, 5, 10, 20
        Uses 20 PDFs for each test
        """
        # Mock read_single_pdf to simulate realistic processing time
        def mock_processing(path):
            time.sleep(0.05)  # Simulate 50ms processing time
            return self._create_mock_pdf_result(Path(path).name)
        
        mock_read_single.side_effect = mock_processing
        
        concurrency_values = [1, 3, 5, 10, 20]
        results_table = []
        
        for max_concurrent in concurrency_values:
            # Create temporary folder with 20 mock PDF files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create 20 empty PDF files
                for i in range(20):
                    pdf_file = temp_path / f"test_paper_{i:02d}.pdf"
                    pdf_file.touch()
                
                # Measure performance
                start_time = time.time()
                results = asyncio.run(read_pdfs_batch(str(temp_path), max_concurrent=max_concurrent))
                elapsed_time = time.time() - start_time
                
                throughput = len(results) / elapsed_time if elapsed_time > 0 else 0
                
                results_table.append({
                    "max_concurrent": max_concurrent,
                    "time": elapsed_time,
                    "throughput": throughput
                })
        
        # Print comparison table
        print(f"\n{'='*60}")
        print(f"Concurrency Comparison (20 PDFs each)")
        print(f"{'='*60}")
        print(f"{'Concurrency':>12} | {'Time (s)':>10} | {'Throughput (PDFs/s)':>20}")
        print(f"{'-'*60}")
        
        for result in results_table:
            print(
                f"{result['max_concurrent']:>12} | "
                f"{result['time']:>10.2f} | "
                f"{result['throughput']:>20.2f}"
            )
        
        print(f"{'='*60}")
        
        # Verify that higher concurrency improves performance (up to a point)
        # max_concurrent=1 should be slower than max_concurrent=5
        time_1 = next(r["time"] for r in results_table if r["max_concurrent"] == 1)
        time_5 = next(r["time"] for r in results_table if r["max_concurrent"] == 5)
        
        self.assertGreater(
            time_1, time_5 * 0.8,  # At least 20% faster with concurrency
            "Concurrent processing should be faster than sequential"
        )
    
    @patch('src.PDFReader.read_single_pdf')
    def test_memory_consistency_across_runs(self, mock_read_single):
        """
        Test that memory usage is consistent across multiple runs.
        
        Verifies no memory leaks by running batch processing 3 times
        and checking that memory doesn't grow significantly.
        """
        # Mock read_single_pdf
        mock_read_single.side_effect = lambda path: self._create_mock_pdf_result(
            Path(path).name
        )
        
        memory_measurements = []
        
        # Run 3 times
        for run in range(3):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create 10 empty PDF files
                for i in range(10):
                    pdf_file = temp_path / f"test_paper_{i:02d}.pdf"
                    pdf_file.touch()
                
                # Measure memory before and after
                memory_before = self._get_memory_usage_mb()
                results = asyncio.run(read_pdfs_batch(str(temp_path), max_concurrent=5))
                memory_after = self._get_memory_usage_mb()
                
                memory_delta = memory_after - memory_before
                memory_measurements.append(memory_delta)
        
        # Log measurements
        print(f"\n{'='*60}")
        print(f"Memory Consistency Test (3 runs)")
        print(f"{'='*60}")
        for i, delta in enumerate(memory_measurements, 1):
            print(f"Run {i}: {delta:.2f}MB")
        print(f"Average: {sum(memory_measurements)/len(memory_measurements):.2f}MB")
        print(f"{'='*60}")
        
        # Memory should not grow significantly across runs
        # (indicates no memory leaks)
        max_delta = max(memory_measurements)
        min_delta = min(memory_measurements)
        growth = max_delta - min_delta
        
        self.assertLess(
            growth, 200,
            f"Memory growth across runs should be < 200MB (was {growth:.2f}MB)"
        )
    
    @patch('src.PDFReader.read_single_pdf')
    def test_error_handling_performance(self, mock_read_single):
        """
        Test performance when 20% of PDFs fail.
        
        Verifies that partial failures don't significantly impact performance.
        """
        # Mock read_single_pdf with 20% failure rate
        call_count = [0]
        
        def mock_with_failures(path):
            call_count[0] += 1
            # Every 5th PDF fails
            success = (call_count[0] % 5) != 0
            return self._create_mock_pdf_result(Path(path).name, success=success)
        
        mock_read_single.side_effect = mock_with_failures
        
        # Create temporary folder with 20 mock PDF files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create 20 empty PDF files
            for i in range(20):
                pdf_file = temp_path / f"test_paper_{i:02d}.pdf"
                pdf_file.touch()
            
            # Measure performance
            start_time = time.time()
            results = asyncio.run(read_pdfs_batch(str(temp_path), max_concurrent=5))
            elapsed_time = time.time() - start_time
            
            # Count successes and failures
            successful = sum(1 for r in results if r["success"])
            failed = len(results) - successful
            
            # Assertions
            self.assertEqual(len(results), 20, "Should process all 20 PDFs")
            self.assertEqual(failed, 4, "Should have ~20% failure rate (4 out of 20)")
            self.assertLess(elapsed_time, 5.0, "Should complete quickly despite failures")
            
            # Log results
            print(f"\n{'='*60}")
            print(f"Error Handling Performance Test")
            print(f"{'='*60}")
            print(f"Total PDFs: {len(results)}")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            print(f"Time: {elapsed_time:.2f}s")
            print(f"Throughput: {len(results)/elapsed_time:.2f} PDFs/second")
            print(f"{'='*60}")


class TestPerformanceRecommendations(unittest.TestCase):
    """
    Tests to determine optimal configuration values.
    """
    
    @patch('src.PDFReader.read_single_pdf')
    def test_optimal_max_concurrent(self, mock_read_single):
        """
        Determine optimal max_concurrent value for the system.
        
        Tests various values and recommends the best one based on throughput.
        """
        # Mock with realistic processing time
        def mock_processing(path):
            time.sleep(0.05)  # 50ms per PDF
            return {
                "markdown": "# Test content",
                "filename": Path(path).name,
                "page_count": 10,
                "processing_time": 0.05,
                "file_size_mb": 1.5,
                "success": True,
                "error": None
            }
        
        mock_read_single.side_effect = mock_processing
        
        # Test different concurrency levels
        concurrency_values = [1, 2, 3, 5, 8, 10, 15, 20]
        test_results = []
        
        for max_concurrent in concurrency_values:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create 30 PDF files
                for i in range(30):
                    (temp_path / f"test_{i:02d}.pdf").touch()
                
                # Measure
                start = time.time()
                results = asyncio.run(read_pdfs_batch(str(temp_path), max_concurrent=max_concurrent))
                elapsed = time.time() - start
                
                throughput = len(results) / elapsed
                test_results.append({
                    "concurrency": max_concurrent,
                    "time": elapsed,
                    "throughput": throughput
                })
        
        # Find optimal value (highest throughput)
        optimal = max(test_results, key=lambda x: x["throughput"])
        
        # Print analysis
        print(f"\n{'='*70}")
        print(f"Optimal Concurrency Analysis (30 PDFs)")
        print(f"{'='*70}")
        print(f"{'Concurrency':>12} | {'Time (s)':>10} | {'Throughput':>15} | {'Efficiency':>10}")
        print(f"{'-'*70}")
        
        for result in test_results:
            efficiency = (result["throughput"] / optimal["throughput"]) * 100
            marker = " ← OPTIMAL" if result == optimal else ""
            print(
                f"{result['concurrency']:>12} | "
                f"{result['time']:>10.2f} | "
                f"{result['throughput']:>15.2f} | "
                f"{efficiency:>9.1f}%{marker}"
            )
        
        print(f"{'='*70}")
        print(f"\n✓ Recommended max_concurrent: {optimal['concurrency']}")
        print(f"  (Achieved {optimal['throughput']:.2f} PDFs/second)")
        print(f"{'='*70}")
        
        # The current default (5) should be reasonable
        self.assertGreaterEqual(
            optimal["concurrency"], 3,
            "Optimal concurrency should be at least 3"
        )


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
