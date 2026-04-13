"""
Token budget allocation engine for optimized LLM context packing.

Allocates token budget across files based on:
- Change status (files that changed get priority)
- Dependency depth (direct dependencies higher than transitive)
- File type (code > tests > docs > config)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class FilePriority(Enum):
    """Priority tier for file inclusion in context."""
    CRITICAL = 4      # Recently changed, core functionality
    HIGH = 3          # Dependencies of changed files
    MEDIUM = 2        # Tests, related code
    LOW = 1           # Documentation, config, assets
    EXCLUDED = 0      # Skip entirely


class FileCategory(Enum):
    """File type categories for implicit priority."""
    CODE = 3
    TEST = 2
    CONFIG = 1
    DOC = 0
    OTHER = 0


@dataclass
class FileInfo:
    """Metadata about a file for budget allocation."""
    path: str
    category: FileCategory
    size_bytes: int
    changed: bool = False
    depth: int = 0  # Dependency depth (0 = direct, 1+ = transitive)
    dependents: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    @property
    def priority(self) -> FilePriority:
        """Calculate priority tier based on attributes."""
        if self.changed:
            return FilePriority.CRITICAL
        if self.depth == 0:  # Direct dependency
            return FilePriority.HIGH
        if self.category == FileCategory.CODE or self.depth == 1:
            return FilePriority.MEDIUM
        return FilePriority.LOW

    def estimate_tokens(self) -> int:
        """Rough estimate: ~4 characters per token on average."""
        return max(50, self.size_bytes // 4)


@dataclass
class BudgetAllocation:
    """Result of budget allocation."""
    allocated_files: List[Tuple[str, int]]  # (path, estimated_tokens)
    total_tokens: int
    remaining_budget: int
    excluded_files: List[str]


class TokenBudgetManager:
    """Manages token budget allocation across files."""

    def __init__(self, total_budget: int = 8000, tier_weights: Optional[Dict[FilePriority, float]] = None):
        """
        Initialize budget manager.
        
        Args:
            total_budget: Total tokens available for context (default 8K, typical for Claude/GPT-4)
            tier_weights: Weight multipliers for each priority tier (default: equal distribution)
        """
        self.total_budget = total_budget
        self.tier_weights = tier_weights or {
            FilePriority.CRITICAL: 0.50,    # 50% for changed files
            FilePriority.HIGH: 0.30,        # 30% for dependencies
            FilePriority.MEDIUM: 0.15,      # 15% for tests/related
            FilePriority.LOW: 0.05,         # 5% for docs
        }

    def allocate(self, files: List[FileInfo], changed_paths: Optional[Set[str]] = None) -> BudgetAllocation:
        """
        Allocate token budget across files using priority tiers.
        
        Args:
            files: List of files to allocate budget for
            changed_paths: Set of file paths that have changed (for diff-first)
            
        Returns:
            BudgetAllocation with allocated files and budget remaining
        """
        if not files:
            return BudgetAllocation([], 0, self.total_budget, [])

        # Mark changed files
        if changed_paths:
            for f in files:
                if f.path in changed_paths:
                    f.changed = True

        # Group files by priority tier
        by_tier = self._group_by_priority(files)

        # Allocate budget per tier
        allocated = []
        remaining = self.total_budget
        excluded = []

        for tier in [FilePriority.CRITICAL, FilePriority.HIGH, FilePriority.MEDIUM, FilePriority.LOW]:
            if tier not in by_tier or remaining <= 0:
                continue

            tier_files = by_tier[tier]
            tier_budget = int(self.total_budget * self.tier_weights[tier])
            tier_allocated, tier_used = self._allocate_tier(tier_files, tier_budget)

            allocated.extend(tier_allocated)
            remaining -= tier_used

        # Track excluded files
        allocated_paths = {p for p, _ in allocated}
        for f in files:
            if f.path not in allocated_paths:
                excluded.append(f.path)

        total_used = self.total_budget - remaining
        return BudgetAllocation(allocated, total_used, remaining, excluded)

    def _group_by_priority(self, files: List[FileInfo]) -> Dict[FilePriority, List[FileInfo]]:
        """Group files by computed priority tier."""
        groups: Dict[FilePriority, List[FileInfo]] = {tier: [] for tier in FilePriority}
        for f in files:
            groups[f.priority].append(f)
        return groups

    def _allocate_tier(self, files: List[FileInfo], tier_budget: int) -> Tuple[List[Tuple[str, int]], int]:
        """
        Allocate budget within a priority tier.
        
        Sorts by size (smallest first) to maximize file count within budget.
        """
        # Sort by size ascending (fit more files within budget)
        sorted_files = sorted(files, key=lambda f: f.estimate_tokens())

        allocated = []
        used = 0

        for f in sorted_files:
            tokens = f.estimate_tokens()
            if used + tokens <= tier_budget:
                allocated.append((f.path, tokens))
                used += tokens
            else:
                # Still try to fit small files
                if tokens < tier_budget * 0.1 and used + tokens <= tier_budget * 1.1:
                    allocated.append((f.path, tokens))
                    used += tokens

        return allocated, used

    def suggest_budget_for_task(self, task_type: str) -> int:
        """Suggest token budget based on task type."""
        budgets = {
            "bug_fix": 6000,        # Focused: specific bug + related tests
            "refactor": 8000,       # Medium: change affects multiple files
            "feature": 10000,       # Large: new functionality + integration
            "test": 4000,           # Small: test file + minimal implementation
            "review": 12000,        # Large: multiple files to understand
        }
        return budgets.get(task_type, self.total_budget)
