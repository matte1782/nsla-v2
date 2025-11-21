# app/prompt_loader.py
"""
Prompt and context file loader for NSLA v2.

This module provides utilities to:
- Load prompt templates from resources/prompts/
- Load context files (ontology YAML, JSON specs, schemas)
- Format prompts with variable injection (handles JSON examples safely)
- Build complete prompts with context for LLM calls
"""

import json
import logging
import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Base paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = PROJECT_ROOT / "resources" / "prompts"
ONTOLOGY_DIR = PROJECT_ROOT / "resources" / "ontology"
SCHEMAS_DIR = PROJECT_ROOT / "resources" / "nsla_v2" / "json" / "schemas"
AGENTS_DIR = PROJECT_ROOT / "resources" / "nsla_v2" / "json" / "agents"


class PromptLoader:
    """
    Utility class for loading and formatting prompts with context files.
    
    Handles:
    - Text prompt templates
    - YAML context files (ontology)
    - JSON context files (specs, schemas)
    - Safe variable substitution (handles JSON examples in templates)
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the prompt loader.
        
        Args:
            project_root: Root directory of the project. If None, auto-detects.
        """
        self.project_root = project_root or PROJECT_ROOT
        self.prompts_dir = self.project_root / "resources" / "prompts"
        self.ontology_dir = self.project_root / "resources" / "ontology"
        self.schemas_dir = self.project_root / "resources" / "nsla_v2" / "json" / "schemas"
        self.agents_dir = self.project_root / "resources" / "nsla_v2" / "json" / "agents"
        
        # Cache for loaded files
        self._cache: Dict[str, Union[str, Dict[str, Any]]] = {}
    
    def load_text_file(self, file_path: Union[str, Path]) -> str:
        """
        Load a text file (prompt template, etc.).
        
        Args:
            file_path: Path to the file (relative to prompts_dir or absolute)
            
        Returns:
            File contents as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        path = Path(file_path)
        if not path.is_absolute():
            # Try relative to prompts_dir first, then project_root
            if (self.prompts_dir / path).exists():
                path = self.prompts_dir / path
            elif (self.project_root / path).exists():
                path = self.project_root / path
            else:
                # Try with just the filename in prompts_dir
                if (self.prompts_dir / path.name).exists():
                    path = self.prompts_dir / path.name
        
        cache_key = f"text:{path}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._cache[cache_key] = content
            logger.debug(f"Loaded text file: {path}")
            return content
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
            raise
        except Exception as e:
            logger.error(f"Error loading file {path}: {e}")
            raise IOError(f"Cannot read file {path}: {e}") from e
    
    def load_yaml_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load a YAML file (ontology, config, etc.).
        
        Args:
            file_path: Path to the file (relative to ontology_dir or absolute)
            
        Returns:
            Parsed YAML as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        path = Path(file_path)
        if not path.is_absolute():
            # Try relative to ontology_dir first, then project_root
            if (self.ontology_dir / path).exists():
                path = self.ontology_dir / path
            elif (self.project_root / path).exists():
                path = self.project_root / path
            else:
                # Try with just the filename
                if (self.ontology_dir / path.name).exists():
                    path = self.ontology_dir / path.name
        
        cache_key = f"yaml:{path}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f) or {}
            self._cache[cache_key] = content
            logger.debug(f"Loaded YAML file: {path}")
            return content
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading YAML file {path}: {e}")
            raise
    
    def load_json_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load a JSON file (specs, schemas, etc.).
        
        Args:
            file_path: Path to the file (relative to agents_dir/schemas_dir or absolute)
            
        Returns:
            Parsed JSON as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is invalid
        """
        path = Path(file_path)
        if not path.is_absolute():
            # Try relative to agents_dir, schemas_dir, then project_root
            if (self.agents_dir / path).exists():
                path = self.agents_dir / path
            elif (self.schemas_dir / path).exists():
                path = self.schemas_dir / path
            elif (self.project_root / path).exists():
                path = self.project_root / path
            else:
                # Try with just the filename
                if (self.agents_dir / path.name).exists():
                    path = self.agents_dir / path.name
                elif (self.schemas_dir / path.name).exists():
                    path = self.schemas_dir / path.name
        
        cache_key = f"json:{path}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = json.load(f)
            self._cache[cache_key] = content
            logger.debug(f"Loaded JSON file: {path}")
            return content
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in {path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading JSON file {path}: {e}")
            raise
    
    def _safe_substitute_variables(
        self,
        template: str,
        variables: Dict[str, Any],
        placeholder_pattern: str = r"\{\{(\w+)\}\}"
    ) -> str:
        """
        Safely substitute variables in template using regex.
        
        This method only substitutes placeholders that match the pattern,
        avoiding conflicts with JSON examples in templates.
        
        By default, uses {{variable}} syntax to avoid conflicts with {variable}
        in JSON examples. If you want to use {variable}, set placeholder_pattern
        to r"\\{(\\w+)\\}" but be aware it may match JSON examples.
        
        Args:
            template: Template string
            variables: Dictionary of variables to substitute
            placeholder_pattern: Regex pattern for placeholders (default: {{var}})
            
        Returns:
            Template with variables substituted
        """
        def replace_var(match):
            var_name = match.group(1)
            if var_name in variables:
                return str(variables[var_name])
            else:
                logger.warning(f"Variable '{var_name}' not found in variables dict")
                return match.group(0)  # Return original placeholder
        
        return re.sub(placeholder_pattern, replace_var, template)
    
    def format_prompt(
        self,
        template: str,
        variables: Optional[Dict[str, Any]] = None,
        context_files: Optional[List[str]] = None,
        use_double_braces: bool = False
    ) -> str:
        """
        Format a prompt template with variable substitution and context.
        
        Args:
            template: Prompt template string
            variables: Dictionary of variables to substitute
            context_files: List of context file paths to include
            use_double_braces: If True, uses {{var}} syntax. If False, tries {var} first,
                             then falls back to safe regex substitution for remaining vars.
            
        Returns:
            Formatted prompt string
        """
        variables = variables or {}
        formatted = template
        
        # Try standard format() first if variables are provided
        if variables:
            if use_double_braces:
                # Use {{var}} syntax - safer for templates with JSON examples
                # First, escape existing {{ to avoid double-escaping
                formatted = formatted.replace("{{", "{{{{").replace("}}", "}}}}")
                # Then replace {{var}} with {var} for format()
                for var_name, var_value in variables.items():
                    placeholder = f"{{{{{var_name}}}}}"
                    formatted = formatted.replace(placeholder, str(var_value))
            else:
                # Use safe regex substitution to avoid conflicts with JSON examples
                formatted = self._safe_substitute_variables(
                    template,
                    variables,
                    placeholder_pattern=r"\{(\w+)\}"
                )
        
        # Append context files if specified
        if context_files:
            context_section = "\n\n---\nCONTEXT FILES:\n"
            for ctx_file in context_files:
                try:
                    if ctx_file.endswith('.yaml') or ctx_file.endswith('.yml'):
                        ctx_content = self.load_yaml_file(ctx_file)
                        context_section += f"\n### {ctx_file} ###\n"
                        context_section += json.dumps(ctx_content, indent=2, ensure_ascii=False)
                        context_section += "\n"
                    elif ctx_file.endswith('.json'):
                        ctx_content = self.load_json_file(ctx_file)
                        context_section += f"\n### {ctx_file} ###\n"
                        context_section += json.dumps(ctx_content, indent=2, ensure_ascii=False)
                        context_section += "\n"
                    else:
                        ctx_content = self.load_text_file(ctx_file)
                        context_section += f"\n### {ctx_file} ###\n"
                        context_section += ctx_content
                        context_section += "\n"
                except Exception as e:
                    logger.warning(f"Could not load context file {ctx_file}: {e}")
                    continue
            
            formatted += context_section
        
        return formatted
    
    def inject_runtime_variables(
        self,
        template: str,
        runtime_data: Dict[str, Any]
    ) -> str:
        """
        Inject runtime variables into a template.
        
        Handles multiple placeholder formats:
        1. {variable} - standard format
        2. "key": "<description>" - JSON example format (replaces <description>)
        3. {{variable}} - double-brace format
        4. <variable> - angle bracket format
        
        This method is designed to work with templates that have JSON examples.
        
        Args:
            template: Template string
            runtime_data: Dictionary with runtime values (e.g., {"question": "...", "canonicalization": {...}})
            
        Returns:
            Template with runtime data injected
        """
        result = template
        
        # For each variable, do smart replacement
        for var_name, var_value in runtime_data.items():
            # Convert value to string representation
            if isinstance(var_value, dict):
                value_str = json.dumps(var_value, indent=2, ensure_ascii=False)
            elif isinstance(var_value, list):
                value_str = json.dumps(var_value, indent=2, ensure_ascii=False)
            else:
                value_str = str(var_value)
            
            # Strategy 1: Replace {var_name} placeholders (standard format)
            pattern1 = rf'\{{(\s*){re.escape(var_name)}(\s*)\}}'
            result = re.sub(pattern1, lambda m: f"{m.group(1)}{value_str}{m.group(2)}", result)
            
            # Strategy 2: Replace "var_name": "<description>" patterns (JSON example format)
            # Pattern: "var_name": "<any description>"
            # This handles cases like: "question": "<Italian legal question about contractual liability>"
            pattern2 = rf'"{re.escape(var_name)}"\s*:\s*"<[^>]*>"'
            replacement2 = f'"{var_name}": "{value_str}"'
            result = re.sub(pattern2, replacement2, result)
            
            # Strategy 3: Replace {{var_name}} placeholders (double-brace format)
            pattern3 = rf'\{{{{(\s*){re.escape(var_name)}(\s*)\}}}}'
            result = re.sub(pattern3, lambda m: f"{m.group(1)}{value_str}{m.group(2)}", result)
            
            # Strategy 4: Replace <var_name> placeholders (angle bracket format)
            pattern4 = rf'<{re.escape(var_name)}>'
            result = re.sub(pattern4, value_str, result)
        
        return result
    
    def load_prompt_with_context(
        self,
        prompt_name: str,
        variables: Optional[Dict[str, Any]] = None,
        include_ontology: bool = True,
        include_specs: Optional[List[str]] = None,
        inject_runtime: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Load a prompt template and format it with context files.
        
        This is a convenience method that:
        1. Loads the prompt template
        2. Automatically includes ontology if requested
        3. Includes specified spec files
        4. Formats with variables (using safe substitution)
        5. Optionally injects runtime data
        
        Args:
            prompt_name: Name of prompt file (e.g., "prompt_phase_2_1_canonicalizer.txt")
            variables: Variables to substitute in template (for {{var}} syntax)
            include_ontology: Whether to include legal_it_v1.yaml
            include_specs: List of spec file names to include
            inject_runtime: Runtime data to inject (e.g., {"question": "..."})
            
        Returns:
            Complete formatted prompt ready for LLM
        """
        # Load prompt template
        template = self.load_text_file(prompt_name)
        
        # Inject runtime variables first (if provided)
        if inject_runtime:
            template = self.inject_runtime_variables(template, inject_runtime)
        
        # Build context files list
        context_files = []
        if include_ontology:
            context_files.append("legal_it_v1.yaml")
        
        if include_specs:
            context_files.extend(include_specs)
        
        # Format with variables and context
        return self.format_prompt(template, variables, context_files, use_double_braces=False)
    
    def get_ontology(self) -> Dict[str, Any]:
        """
        Get the legal ontology.
        
        Returns:
            Parsed ontology YAML
        """
        return self.load_yaml_file("legal_it_v1.yaml")
    
    def clear_cache(self):
        """Clear the file cache."""
        self._cache.clear()
        logger.debug("Prompt loader cache cleared")


# Global instance for convenience
_default_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """
    Get the default prompt loader instance (singleton pattern).
    
    Returns:
        PromptLoader instance
    """
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader


# Convenience functions
def load_prompt(prompt_name: str, **kwargs) -> str:
    """
    Convenience function to load a prompt.
    
    Args:
        prompt_name: Name of prompt file
        **kwargs: Additional arguments passed to load_prompt_with_context
        
    Returns:
        Formatted prompt string
    """
    loader = get_prompt_loader()
    return loader.load_prompt_with_context(prompt_name, **kwargs)


def load_ontology() -> Dict[str, Any]:
    """
    Convenience function to load the ontology.
    
    Returns:
        Parsed ontology YAML
    """
    loader = get_prompt_loader()
    return loader.get_ontology()


__all__ = [
    "PromptLoader",
    "get_prompt_loader",
    "load_prompt",
    "load_ontology",
]