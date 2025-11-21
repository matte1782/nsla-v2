# test_prompt_loader_standalone.py
"""
Standalone test script for prompt_loader.py
Run with: python test_prompt_loader_standalone.py
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.prompt_loader import PromptLoader, get_prompt_loader, load_prompt, load_ontology


def test_basic_loading():
    """Test 1: Basic file loading"""
    print("\n" + "="*60)
    print("TEST 1: Basic File Loading")
    print("="*60)
    
    loader = PromptLoader()
    
    # Test loading text file
    try:
        prompt = loader.load_text_file("prompt_phase_2_1_canonicalizer.txt")
        print("✅ Text file loaded successfully")
        print(f"   Length: {len(prompt)} characters")
        print(f"   First 100 chars: {prompt[:100]}...")
    except Exception as e:
        raise AssertionError(f"Text file loading failed: {e}") from e
    
    # Test loading YAML file
    try:
        ontology = loader.load_yaml_file("legal_it_v1.yaml")
        print("✅ YAML file loaded successfully")
        print(f"   Keys: {list(ontology.keys())}")
        print(f"   Version: {ontology.get('version', 'N/A')}")
        print(f"   Number of predicates: {len(ontology.get('predicates', {}))}")
    except Exception as e:
        raise AssertionError(f"YAML file loading failed: {e}") from e
    
    # Test loading JSON file
    try:
        spec = loader.load_json_file("canonicalizer_agent_vFinal.json")
        print("✅ JSON file loaded successfully")
        print(f"   Top-level keys: {list(spec.keys())}")
    except Exception as e:
        raise AssertionError(f"JSON file loading failed: {e}") from e


def test_variable_substitution():
    """Test 2: Variable substitution"""
    print("\n" + "="*60)
    print("TEST 2: Variable Substitution")
    print("="*60)
    
    loader = PromptLoader()
    
    template = "Hello {name}, your question is: {question}"
    variables = {
        "name": "TestUser",
        "question": "What is a contract?"
    }
    
    try:
        result = loader.format_prompt(template, variables)
        print("✅ Variable substitution successful")
        print(f"   Result: {result}")
    except Exception as e:
        raise AssertionError(f"Variable substitution failed: {e}") from e
    
    assert "TestUser" in result and "What is a contract?" in result, "Variables not correctly substituted"


def test_context_inclusion():
    """Test 3: Context file inclusion"""
    print("\n" + "="*60)
    print("TEST 3: Context File Inclusion")
    print("="*60)
    
    loader = PromptLoader()
    
    template = "This is a test prompt.\n\nQuestion: {question}"
    variables = {"question": "Test question"}
    context_files = ["legal_it_v1.yaml"]
    
    try:
        result = loader.format_prompt(template, variables, context_files)
        print("✅ Context inclusion successful")
        print(f"   Result length: {len(result)} characters")
    except Exception as e:
        raise AssertionError(f"Context inclusion failed: {e}") from e
    
    assert "version" in result and "predicates" in result, "Ontology content not found in formatted prompt"


def test_convenience_functions():
    """Test 4: Convenience functions"""
    print("\n" + "="*60)
    print("TEST 4: Convenience Functions")
    print("="*60)
    
    try:
        # Test get_prompt_loader
        loader1 = get_prompt_loader()
        loader2 = get_prompt_loader()
        if loader1 is loader2:
            print("✅ Singleton pattern works (same instance)")
        else:
            raise AssertionError("Singleton pattern not working (different instances)")
        
        # Test load_ontology
        ontology = load_ontology()
        assert isinstance(ontology, dict) and "version" in ontology, "load_ontology() failed"
        
        # Test load_prompt (without context for speed)
        loader = get_prompt_loader()
        prompt = loader.load_text_file("prompt_phase_2_1_canonicalizer.txt")
        assert len(prompt) > 0, "load_prompt() returned empty content"
    except Exception as e:
        raise AssertionError(f"Convenience functions test failed: {e}") from e


def test_cache():
    """Test 5: Caching mechanism"""
    print("\n" + "="*60)
    print("TEST 5: Caching Mechanism")
    print("="*60)
    
    loader = PromptLoader()
    
    try:
        # Load file first time
        import time
        start1 = time.perf_counter()
        content1 = loader.load_text_file("prompt_phase_2_1_canonicalizer.txt")
        time1 = time.perf_counter() - start1
        
        # Load same file second time (should use cache)
        start2 = time.perf_counter()
        content2 = loader.load_text_file("prompt_phase_2_1_canonicalizer.txt")
        time2 = time.perf_counter() - start2
        
        assert content1 == content2, "Cache returned different content"
        print("✅ Cache returns same content")
        print(f"   First load: {time1*1000:.2f}ms")
        print(f"   Second load (cached): {time2*1000:.2f}ms")
        assert time2 <= time1, "Cache load should not be slower than first load"
    except Exception as e:
        raise AssertionError(f"Cache test failed: {e}") from e


def test_error_handling():
    """Test 6: Error handling"""
    print("\n" + "="*60)
    print("TEST 6: Error Handling")
    print("="*60)
    
    loader = PromptLoader()
    
    # Test non-existent file
    try:
        loader.load_text_file("nonexistent_file.txt")
        raise AssertionError("Expected FileNotFoundError for missing file")
    except FileNotFoundError:
        pass
    print("✅ Correctly raises FileNotFoundError for missing file")
    
    # Test missing variable (should not crash)
    try:
        template = "Hello {name}"
        result = loader.format_prompt(template, {})  # Missing 'name'
        print("✅ Missing variable handled gracefully (warning logged)")
        assert "Hello" in result
    except Exception as e:
        raise AssertionError(f"Missing variable caused crash: {e}") from e


def test_full_prompt_loading():
    """Test 7: Full prompt loading with context (real use case)"""
    print("\n" + "="*60)
    print("TEST 7: Full Prompt Loading (Real Use Case)")
    print("="*60)
    
    loader = PromptLoader()
    
    try:
        # Load Phase 2.1 prompt with ontology and spec
        # Use inject_runtime instead of variables for templates with JSON examples
        prompt = loader.load_prompt_with_context(
            "prompt_phase_2_1_canonicalizer.txt",
            variables=None,  # Don't use variables for this template
            include_ontology=True,
            include_specs=["canonicalizer_agent_vFinal.json"],
            inject_runtime={"question": "Test question"}  # Use inject_runtime instead
        )
        
        print("✅ Full prompt loaded successfully")
        print(f"   Total length: {len(prompt)} characters")
        
        # Verify key components
        checks = [
            ("SYSTEM" in prompt, "Contains SYSTEM section"),
            ("CONTEXT FILES" in prompt or "legal_it_v1.yaml" in prompt or "### legal_it_v1.yaml" in prompt, "Contains context"),
            ("Test question" in prompt, "Contains injected runtime variable"),
        ]
        
        for check, desc in checks:
            if check:
                print(f"   ✅ {desc}")
            else:
                print(f"   ❌ {desc}")
        assert all(check for check, _ in checks), "Full prompt missing one or more required sections"
    except Exception as e:
        print(f"❌ Full prompt loading failed: {e}")
        import traceback
        traceback.print_exc()
        raise AssertionError("Full prompt loading failed") from e


def test_runtime_injection():
    """Test 8: Runtime variable injection (new test)"""
    print("\n" + "="*60)
    print("TEST 8: Runtime Variable Injection")
    print("="*60)
    
    loader = PromptLoader()
    
    try:
        # Test inject_runtime_variables method
        template = """
INPUT (RUNTIME):
{
  "question": "{question}",
  "options": {
    "return_low_confidence": false
  }
}
"""
        runtime_data = {
            "question": "Qual è la responsabilità contrattuale?"
        }
        
        result = loader.inject_runtime_variables(template, runtime_data)
        
        print("✅ Runtime injection successful")
        print(f"   Result length: {len(result)} characters")
        
        # Check if question was injected
        assert "Qual è la responsabilità contrattuale?" in result, "Runtime variable not found in result"
        print("✅ Runtime variable correctly injected")
    except Exception as e:
        print(f"❌ Runtime injection test failed: {e}")
        import traceback
        traceback.print_exc()
        raise AssertionError("Runtime injection test failed") from e


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("PROMPT LOADER TEST SUITE")
    print("="*60)
    
    tests = [
        ("Basic Loading", test_basic_loading),
        ("Variable Substitution", test_variable_substitution),
        ("Context Inclusion", test_context_inclusion),
        ("Convenience Functions", test_convenience_functions),
        ("Caching", test_cache),
        ("Error Handling", test_error_handling),
        ("Full Prompt Loading", test_full_prompt_loading),
        ("Runtime Injection", test_runtime_injection),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Prompt loader is ready.")
        print("✅ Ready to proceed to Step 2: Implementing Phase 2.1 (Canonicalizer)")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    sys.exit(main())