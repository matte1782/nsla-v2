# tests/test_prompt_loader.py
"""
Pytest tests for prompt_loader.py
Run with: pytest tests/test_prompt_loader.py -v
"""

import pytest
from pathlib import Path
from app.prompt_loader import PromptLoader, get_prompt_loader, load_ontology


class TestPromptLoader:
    """Test suite for PromptLoader class"""
    
    def test_load_text_file(self):
        """Test loading a text prompt file"""
        loader = PromptLoader()
        prompt = loader.load_text_file("prompt_phase_2_1_canonicalizer.txt")
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "SYSTEM" in prompt or "Prompt" in prompt
    
    def test_load_yaml_file(self):
        """Test loading YAML ontology file"""
        loader = PromptLoader()
        ontology = loader.load_yaml_file("legal_it_v1.yaml")
        
        assert isinstance(ontology, dict)
        assert "version" in ontology
        assert "predicates" in ontology
        assert ontology["version"] == "1.0"
    
    def test_load_json_file(self):
        """Test loading JSON spec file"""
        loader = PromptLoader()
        spec = loader.load_json_file("canonicalizer_agent_vFinal.json")
        
        assert isinstance(spec, dict)
        assert len(spec) > 0
    
    def test_format_prompt_with_variables(self):
        """Test variable substitution in prompts"""
        loader = PromptLoader()
        template = "Hello {name}, question: {question}"
        variables = {"name": "Test", "question": "What is X?"}
        
        result = loader.format_prompt(template, variables)
        
        assert "Test" in result
        assert "What is X?" in result
        assert "{name}" not in result
        assert "{question}" not in result
    
    def test_format_prompt_with_context(self):
        """Test prompt formatting with context files"""
        loader = PromptLoader()
        template = "Test prompt with {question}"
        variables = {"question": "test"}
        context = ["legal_it_v1.yaml"]
        
        result = loader.format_prompt(template, variables, context)
        
        assert "test" in result
        assert "version" in result or "predicates" in result
    
    def test_load_prompt_with_context(self):
        """Test convenience method for loading prompt with context"""
        loader = PromptLoader()
        prompt = loader.load_prompt_with_context(
            "prompt_phase_2_1_canonicalizer.txt",
            variables={"question": "test"},
            include_ontology=True
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 100
    
    def test_cache_mechanism(self):
        """Test that caching works"""
        loader = PromptLoader()
        
        # First load
        content1 = loader.load_text_file("prompt_phase_2_1_canonicalizer.txt")
        
        # Second load should use cache
        content2 = loader.load_text_file("prompt_phase_2_1_canonicalizer.txt")
        
        assert content1 == content2
    
    def test_clear_cache(self):
        """Test cache clearing"""
        loader = PromptLoader()
        loader.load_text_file("prompt_phase_2_1_canonicalizer.txt")
        
        assert len(loader._cache) > 0
        loader.clear_cache()
        assert len(loader._cache) == 0
    
    def test_file_not_found(self):
        """Test error handling for missing files"""
        loader = PromptLoader()
        
        with pytest.raises(FileNotFoundError):
            loader.load_text_file("nonexistent_file_12345.txt")
    
    def test_get_ontology(self):
        """Test get_ontology method"""
        loader = PromptLoader()
        ontology = loader.get_ontology()
        
        assert isinstance(ontology, dict)
        assert "version" in ontology
        assert "predicates" in ontology


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_get_prompt_loader_singleton(self):
        """Test that get_prompt_loader returns singleton"""
        loader1 = get_prompt_loader()
        loader2 = get_prompt_loader()
        
        assert loader1 is loader2
    
    def test_load_ontology_function(self):
        """Test load_ontology convenience function"""
        ontology = load_ontology()
        
        assert isinstance(ontology, dict)
        assert "version" in ontology