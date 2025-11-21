# tests/test_benchmark_smoke.py
import pytest
import json
from unittest.mock import patch, MagicMock
from app import benchmark
from pathlib import Path


def test_load_cases_non_empty():
    """Test that load_cases returns a non-empty list of cases."""
    # Create a minimal test case file
    test_cases = [
        {
            "id": "test_001",
            "question": "Test question?",
            "gold_answer": "Test answer",
            "tags": ["test"]
        }
    ]
    
    test_file = Path("data/test_cases.json")
    test_file.parent.mkdir(exist_ok=True)
    with open(test_file, 'w') as f:
        json.dump(test_cases, f)
    
    try:
        cases = benchmark.load_cases(str(test_file))
        assert isinstance(cases, list)
        assert len(cases) > 0
        assert "id" in cases[0]
        assert "question" in cases[0] 
        assert "gold_answer" in cases[0]
        assert "tags" in cases[0]
    finally:
        # Cleanup
        test_file.unlink(missing_ok=True)


def test_run_benchmark_returns_stats():
    """Test that run_benchmark returns expected statistics structure."""
    # Mock load_cases to return a test case
    with patch.object(benchmark, 'load_cases') as mock_load:
        mock_load.return_value = [
            {
                "id": "test_001",
                "question": "Test question?",
                "gold_answer": "Test answer",
                "tags": ["test"]
            }
        ]
        
        # Mock HTTP responses to return successful responses
        with patch('app.benchmark.requests.post') as mock_post:
            # Mock /llm_only response
            llm_mock = MagicMock()
            llm_mock.status_code = 200
            llm_mock.json.return_value = {"answer": "Test LLM answer"}
            
            # Mock /legal_query response
            nsla_mock = MagicMock()
            nsla_mock.status_code = 200
            nsla_mock.json.return_value = {
                "answer": "Test NSLA answer",
                "verified": True,
                "final_answer": "Test final answer"
            }

            # Mock /legal_query_v2 response
            v2_mock = MagicMock()
            v2_mock.status_code = 200
            v2_mock.json.return_value = {
                "final_answer": "Test answer v2",
                "feedback": {
                    "status": "consistent_entails",
                    "missing_links": [],
                    "conflicting_axioms": []
                },
                "guardrail": {"ok": True, "issues": []},
                "explanation": {"summary": "All good"},
                "phase2": {"feedback_v1": {"status": "consistent_no_entailment"}},
                "fallback_used": False
            }

            # Mock /legal_query_v2_iterative response
            iter_mock = MagicMock()
            iter_mock.status_code = 200
            iter_mock.json.return_value = {
                "mode": "v2_iterative",
                "best": {
                    "iteration": 1,
                    "final_answer": "Test answer iter",
                    "feedback": {
                        "status": "consistent_entails",
                        "missing_links": [],
                        "conflicting_axioms": []
                    },
                    "guardrail": {"ok": True, "issues": []}
                },
                "history": [
                    {"iteration": 0, "status": "consistent_no_entailment", "missing_links": ["X"], "conflicting_axioms": []},
                    {"iteration": 1, "status": "consistent_entails", "missing_links": [], "conflicting_axioms": []}
                ]
            }
            
            # Configure side effects for the four calls
            mock_post.side_effect = [llm_mock, nsla_mock, v2_mock, iter_mock]
            
            result = benchmark.run_benchmark(
                base_url="http://fake",
                cases_path="fake_cases.json"
            )
            
            # Verify structure
            assert isinstance(result, dict)
            assert "n_cases" in result
            assert "n_success" in result
            assert "n_fail" in result
            assert "llm_only_accuracy" in result
            assert "nsla_accuracy" in result
            assert "nsla_v2_accuracy" in result  # nuove metriche Phase 2
            assert "nsla_iter_accuracy" in result
            assert "v2_guardrail_pass_rate" in result
            assert "iter_guardrail_pass_rate" in result
            assert "tag_stats" in result
            assert "avg_llm_only_time" in result
            assert "avg_nsla_time" in result
            assert "details" in result
            assert "error" in result  # New field
            
            # Verify values
            assert result["n_cases"] == 1
            assert result["n_success"] == 1
            assert result["n_fail"] == 0
            assert isinstance(result["llm_only_accuracy"], (int, float))
            assert isinstance(result["nsla_accuracy"], (int, float))
            assert isinstance(result["v2_guardrail_pass_rate"], (int, float))
            assert isinstance(result["tag_stats"], list)
            assert result["error"] is None  # Should be None in success case


def test_run_benchmark_handles_http_errors(monkeypatch):
    """Test that run_benchmark handles HTTP errors gracefully."""
    # Mock load_cases to return a test case
    with patch.object(benchmark, 'load_cases') as mock_load:
        mock_load.return_value = [
            {
                "id": "test_001",
                "question": "Test question?",
                "gold_answer": "Test answer",
                "tags": ["test"]
            }
        ]
        
        # Mock HTTP response to simulate server error
        with patch('app.benchmark.requests.post') as mock_post:
            error_mock = MagicMock()
            error_mock.status_code = 500
            error_mock.json.return_value = {"detail": "Internal Server Error"}
            
            # Configure to always return error
            mock_post.return_value = error_mock
            
            result = benchmark.run_benchmark(
                base_url="http://fake",
                cases_path="fake_cases.json"
            )
            
            # Verify that the error was handled correctly
            assert result["n_cases"] == 1
            assert result["n_success"] == 0
            assert result["n_fail"] == 1
            assert result["nsla_accuracy"] == 0.0
            assert result["error"] is not None  # Should have error info
            assert "HTTP 500" in result["error"]


def test_run_benchmark_handles_connection_errors(monkeypatch):
    """Test that run_benchmark handles connection errors gracefully."""
    # Mock load_cases to return a test case
    with patch.object(benchmark, 'load_cases') as mock_load:
        mock_load.return_value = [
            {
                "id": "test_001", 
                "question": "Test question?",
                "gold_answer": "Test answer",
                "tags": ["test"]
            }
        ]
        
        # Mock requests.post to raise connection error
        with patch('app.benchmark.requests.post') as mock_post:
            mock_post.side_effect = ConnectionError("Connection failed")
            
            result = benchmark.run_benchmark(
                base_url="http://fake",
                cases_path="fake_cases.json"
            )
            
            # Verify that connection errors are handled
            assert result["n_cases"] == 1
            assert result["n_success"] == 0  
            assert result["n_fail"] >= 1  # At least one failure
            assert "error" in result
            assert result["error"] is not None  # Should have error info
            assert "Connection failed" in result["error"]


def test_run_benchmark_handles_file_errors(monkeypatch):
    """Test that run_benchmark handles file loading errors gracefully."""
    # Mock load_cases to raise an exception
    with patch.object(benchmark, 'load_cases') as mock_load:
        mock_load.side_effect = FileNotFoundError("File not found")
        
        result = benchmark.run_benchmark(
            base_url="http://fake",
            cases_path="nonexistent_file.json"
        )
        
        # Verify that file errors are handled
        assert result["n_cases"] == 0
        assert result["n_success"] == 0
        assert result["n_fail"] == 0  # No cases were processed
        assert "error" in result
        assert result["error"] is not None
        assert "Impossibile caricare i casi" in result["error"]


def test_is_correct_function():
    """Test the is_correct function works as expected."""
    # Test exact match
    assert benchmark.is_correct("This is the answer", "This is the answer") is True
    
    # Test case insensitive
    assert benchmark.is_correct("This is the ANSWER", "this is the answer") is True
    
    # Test substring
    assert benchmark.is_correct("The quick brown fox", "quick") is True
    
    # Test no match
    assert benchmark.is_correct("The quick brown fox", "elephant") is False


def test_run_benchmark_empty_cases(monkeypatch):
    """Test that run_benchmark handles empty cases list correctly."""
    # Mock load_cases to return empty list
    with patch.object(benchmark, 'load_cases') as mock_load:
        mock_load.return_value = []
        
        result = benchmark.run_benchmark(
            base_url="http://fake",
            cases_path="empty_cases.json"
        )
        
        # Verify that empty cases are handled
        assert result["n_cases"] == 0
        assert result["n_success"] == 0
        assert result["n_fail"] == 0
        assert "error" in result
        assert result["error"] is not None
        assert "Nessun caso di test trovato" in result["error"]
