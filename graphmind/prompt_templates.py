"""
Prompt templates for LLM queries with optimized token efficiency.

Pre-structured formats for common development tasks:
- bug_fix: Focused investigation with test reproduction
- feature: New functionality description with requirements
- refactor: Code restructuring with impact analysis
- test: Test writing with coverage goals
- review: Code review with quality checks
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class TaskType(Enum):
    """Supported task types for templates."""
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TEST = "test"
    REVIEW = "review"
    OPTIMIZE = "optimize"


@dataclass
class PromptTemplate:
    """Template for a specific task type."""
    task_type: TaskType
    name: str
    description: str
    sections: List[str]  # Ordered sections to include
    required_contexts: List[str]  # What context types are needed
    token_hint: int  # Estimated tokens for complete response
    example_prompt: str


class PromptTemplateRegistry:
    """Registry of optimized prompt templates."""
    
    def __init__(self):
        """Initialize with built-in templates."""
        self.templates: Dict[TaskType, PromptTemplate] = {}
        self._register_templates()
    
    def _register_templates(self):
        """Register all built-in templates."""
        
        # BUG FIX template
        self.templates[TaskType.BUG_FIX] = PromptTemplate(
            task_type=TaskType.BUG_FIX,
            name="Bug Fix Investigation",
            description="Focused debugging with minimal iterations",
            sections=[
                "## Problem",
                "## Current Behavior",
                "## Expected Behavior",
                "## Relevant Code",
                "## Test Case",
                "## Questions for you:",
                "## Proposed Fix",
            ],
            required_contexts=["changed_files", "error_trace", "test_case"],
            token_hint=2000,
            example_prompt="""## Problem
User reports: [error message]

## Current Behavior
The application crashes when [action].

## Expected Behavior
Should [expected result].

## Relevant Code
[snippet with bug]

## Test Case
[failing test]

## Fix Investigation
1. What's the root cause?
2. Is there a minimal fix?
3. Any side effects to check?"""
        )
        
        # FEATURE template
        self.templates[TaskType.FEATURE] = PromptTemplate(
            task_type=TaskType.FEATURE,
            name="Feature Implementation",
            description="New functionality with architecture guidance",
            sections=[
                "## Feature Request",
                "## Requirements",
                "## Design Constraints",
                "## Integration Points",
                "## Implementation Steps",
                "## Success Criteria",
            ],
            required_contexts=["architecture", "related_code", "dependencies"],
            token_hint=3000,
            example_prompt="""## Feature Request
Add [feature name] to [component].

## Requirements
- [requirement 1]
- [requirement 2]
- [requirement 3]

## Design Constraints
- Must integrate with [existing system]
- Should not break [existing functionality]

## Integration Points
Current architecture has [context from graph].

## Implementation Approach
1. Modify [module]
2. Add [new module]
3. Update [integration point]"""
        )
        
        # REFACTOR template
        self.templates[TaskType.REFACTOR] = PromptTemplate(
            task_type=TaskType.REFACTOR,
            name="Code Refactoring",
            description="Restructuring with safety validation",
            sections=[
                "## Current Structure",
                "## Problems with Current Code",
                "## Target Structure",
                "## Safety Checks",
                "## Refactoring Steps",
                "## Testing Strategy",
            ],
            required_contexts=["full_files", "test_coverage", "dependencies"],
            token_hint=3000,
            example_prompt="""## Current Structure
[current implementation overview]

## Problems
- [problem 1: complexity]
- [problem 2: maintainability]
- [problem 3: performance]

## Target Structure
Replace [current] with [proposed].

## Safety Checks
1. Run existing tests first
2. Check [interface] stability
3. Verify [performance] impact

## Validation
- All tests pass: [test file list]
- Performance: [metric unchanged]"""
        )
        
        # TEST template
        self.templates[TaskType.TEST] = PromptTemplate(
            task_type=TaskType.TEST,
            name="Test Implementation",
            description="Test writing with coverage targets",
            sections=[
                "## Code to Test",
                "## Test Objectives",
                "## Test Cases",
                "## Edge Cases",
                "## Execution Strategy",
            ],
            required_contexts=["target_code", "test_framework", "coverage_goals"],
            token_hint=1500,
            example_prompt="""## Code to Test
[function/class definition]

## Test Objectives
- Verify [behavior 1]
- Verify [behavior 2]
- Edge case: [edge case]

## Test Cases
1. Happy path: [scenario]
2. Error case: [scenario]
3. Boundary: [scenario]

## Expected Coverage
Target: [current]% → [target]%"""
        )
        
        # REVIEW template
        self.templates[TaskType.REVIEW] = PromptTemplate(
            task_type=TaskType.REVIEW,
            name="Code Review",
            description="Comprehensive review with security/quality focus",
            sections=[
                "## Code Summary",
                "## Reviewed Files",
                "## Quality Checks",
                "## Security Scan",
                "## Performance Impact",
                "## Recommendations",
            ],
            required_contexts=["full_files", "architecture", "standards"],
            token_hint=2500,
            example_prompt="""## Code Summary
[what changed]

## Files Changed
[file list with line counts]

## Quality Questions
1. Is the code readable and maintainable?
2. Are there code smells?
3. Is error handling adequate?

## Security Checklist
- [ ] Input validation
- [ ] SQL injection risk
- [ ] XSS protection
- [ ] Secrets exposure

## Performance
[impact assessment]"""
        )
        
        # OPTIMIZE template
        self.templates[TaskType.OPTIMIZE] = PromptTemplate(
            task_type=TaskType.OPTIMIZE,
            name="Performance Optimization",
            description="Identify and fix bottlenecks",
            sections=[
                "## Current Performance",
                "## Bottleneck Analysis",
                "## Optimization Options",
                "## Implementation Plan",
                "## Benchmarking Strategy",
            ],
            required_contexts=["metrics", "profiling_data", "target_code"],
            token_hint=2000,
            example_prompt="""## Current Performance
Metric: [value], Baseline: [baseline]

## Bottleneck
Profiling shows [hot spot].

## Optimization Candidates
1. [option 1]: Risk low, Impact medium
2. [option 2]: Risk medium, Impact high

## Implementation
1. Apply [optimization 1]
2. Measure [metric]
3. If < [threshold], apply [optimization 2]"""
        )
    
    def get_template(self, task_type: TaskType) -> Optional[PromptTemplate]:
        """Retrieve template by task type."""
        return self.templates.get(task_type)
    
    def format_prompt(
        self,
        task_type: TaskType,
        context_data: Dict[str, str],
    ) -> str:
        """
        Format a prompt using template sections.
        
        Args:
            task_type: Task type for template selection
            context_data: Mapping of section names to content
            
        Returns:
            Formatted prompt string
        """
        template = self.get_template(task_type)
        if not template:
            return ""
        
        prompt_parts = []
        for section in template.sections:
            section_key = section.replace("## ", "").lower().replace(" ", "_")
            if section_key in context_data:
                prompt_parts.append(section)
                prompt_parts.append(context_data[section_key])
                prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def suggest_context_needs(self, task_type: TaskType) -> List[str]:
        """Get recommended context components for a task."""
        template = self.get_template(task_type)
        return template.required_contexts if template else []
    
    def estimate_response_tokens(self, task_type: TaskType) -> int:
        """Estimate tokens needed for expected response."""
        template = self.get_template(task_type)
        return template.token_hint if template else 1000


# Convenience functions
_registry = PromptTemplateRegistry()


def get_template(task_type: str) -> Optional[PromptTemplate]:
    """Get template by task type string."""
    try:
        task = TaskType(task_type)
        return _registry.get_template(task)
    except ValueError:
        return None


def format_prompt(task_type: str, context_data: Dict[str, str]) -> str:
    """Format a prompt using context data."""
    try:
        task = TaskType(task_type)
        return _registry.format_prompt(task, context_data)
    except ValueError:
        return ""


def suggested_contexts(task_type: str) -> List[str]:
    """Get context suggestions for task."""
    try:
        task = TaskType(task_type)
        return _registry.suggest_context_needs(task)
    except ValueError:
        return []
