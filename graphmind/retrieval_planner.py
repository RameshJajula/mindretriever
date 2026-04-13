"""
Retrieval planner for tiered context delivery.

Implements three tiers of context with increasing cost:
- Tier 1: Graph summary (cheap) - nodes, edges, communities
- Tier 2: Code snippets (medium) - selected lines from changed files
- Tier 3: Full sections (expensive) - complete file content (fallback only)

Uses context gating to minimize token expansion.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import re


class RetrievalTier(Enum):
    """Context retrieval tier."""
    GRAPH_SUMMARY = 1      # Minimal: graph structure only
    SNIPPETS = 2           # Medium: code snippets from key functions
    FULL_FILES = 3         # Maximum: complete file content


@dataclass
class ContextSnippet:
    """A code snippet for context."""
    file_path: str
    start_line: int
    end_line: int
    content: str
    reason: str  # Why this snippet was selected (e.g., "contains_bug", "is_dependency")


@dataclass
class TieredContext:
    """Context delivered in tiers."""
    tier: RetrievalTier
    graph_summary: Optional[Dict] = None          # Tier 1: graph data
    code_snippets: List[ContextSnippet] = None    # Tier 2: code excerpts
    full_files: Dict[str, str] = None             # Tier 3: full content
    total_tokens: int = 0
    
    def __post_init__(self):
        if self.code_snippets is None:
            self.code_snippets = []
        if self.full_files is None:
            self.full_files = {}


class ContextGate:
    """Determines if expanded context is needed."""
    
    @staticmethod
    def should_expand(query: str, current_context_tokens: int, budget: int, tier: RetrievalTier) -> bool:
        """
        Check if context should expand to next tier.
        
        Args:
            query: User's task description
            current_context_tokens: Tokens used in current tier
            budget: Total token budget
            tier: Current tier
            
        Returns:
            True if should expand, False if sufficient
        """
        # Expansion indicators in query
        expansion_queries = [
            r'debug|bug|issue|error|fix|problem',  # Bug-fixing needs more context
            r'refactor|rewrite|restructure',        # Refactoring needs dependencies
            r'integrate|connect|liaison',           # Integration needs system overview
            r'review|audit|security',               # Review needs comprehensive view
        ]
        
        needs_detail = any(re.search(p, query, re.I) for p in expansion_queries)
        
        # Never expand beyond tier 3
        if tier == RetrievalTier.FULL_FILES:
            return False
        
        # Expand if we have budget and query suggests need
        remaining = budget - current_context_tokens
        min_tier_budget = {
            RetrievalTier.GRAPH_SUMMARY: 2000,
            RetrievalTier.SNIPPETS: 3000,
            RetrievalTier.FULL_FILES: 5000,
        }
        
        if tier in min_tier_budget and remaining >= min_tier_budget[tier]:
            return needs_detail or current_context_tokens < budget * 0.3
        
        return False


class RetrieverPlanner:
    """Plans and delivers optimized context in tiers."""
    
    def __init__(self, token_budget: int = 8000):
        """Initialize retriever."""
        self.token_budget = token_budget
        self.gate = ContextGate()
    
    def plan_retrieval(
        self,
        task_type: str,
        query: str,
        graph_data: Dict,
        changed_files: Set[str],
        available_files: Dict[str, str],
        file_metadata: Dict[str, Dict],
    ) -> TieredContext:
        """
        Plan context retrieval based on task and available data.
        
        Args:
            task_type: Task category (bug_fix, feature, refactor, etc.)
            query: User's specific request
            graph_data: Full knowledge graph (nodes, edges, communities)
            changed_files: Set of recently changed file paths
            available_files: Mapping of file path to content
            file_metadata: Mapping of file path to metadata (size, dependencies)
            
        Returns:
            TieredContext with selected tier and content
        """
        # Start with Tier 1 (always cheap)
        context = TieredContext(tier=RetrievalTier.GRAPH_SUMMARY)
        context.graph_summary = self._compress_graph(graph_data)
        tokens_used = self._estimate_tokens(context.graph_summary)
        
        # Try to expand to Tier 2 (snippets)
        if self.gate.should_expand(query, tokens_used, self.token_budget, RetrievalTier.GRAPH_SUMMARY):
            context.tier = RetrievalTier.SNIPPETS
            snippets = self._extract_snippets(
                changed_files,
                available_files,
                file_metadata,
                self.token_budget - tokens_used,
            )
            context.code_snippets = snippets
            tokens_used += self._estimate_tokens(snippets)
        
        # Try to expand to Tier 3 (full files) - only for complex tasks
        if self._is_complex_task(task_type) and self.gate.should_expand(
            query, tokens_used, self.token_budget, RetrievalTier.SNIPPETS
        ):
            context.tier = RetrievalTier.FULL_FILES
            full_content = self._get_full_files(
                changed_files,
                available_files,
                self.token_budget - tokens_used,
            )
            context.full_files = full_content
            tokens_used += self._estimate_tokens(full_content)
        
        context.total_tokens = tokens_used
        return context
    
    def _compress_graph(self, graph_data: Dict) -> Dict:
        """
        Compress graph to summary format (cost: ~500 tokens).
        
        Returns top-level stats without full edge lists.
        """
        return {
            "nodes_count": len(graph_data.get("nodes", [])),
            "edges_count": len(graph_data.get("edges", [])),
            "communities": len(graph_data.get("communities", [])),
            "top_hubs": graph_data.get("top_hubs", [])[:5],  # Top 5 only
            "summary": f"Graph with {len(graph_data.get('nodes', []))} nodes, "
                       f"{len(graph_data.get('communities', []))} communities",
        }
    
    def _extract_snippets(
        self,
        changed_files: Set[str],
        available_files: Dict[str, str],
        file_metadata: Dict[str, Dict],
        budget: int,
    ) -> List[ContextSnippet]:
        """
        Extract code snippets from changed files (cost: ~1500-3000 tokens).
        
        Selects function/class definitions and key sections.
        """
        snippets = []
        tokens_used = 0
        
        for file_path in changed_files:
            if file_path not in available_files or tokens_used >= budget:
                continue
            
            content = available_files[file_path]
            
            # Extract top-level functions/classes (rough heuristic)
            extracted = self._extract_functions(content, file_path, budget - tokens_used)
            snippets.extend(extracted)
            tokens_used += self._estimate_tokens(extracted)
        
        return snippets
    
    def _extract_functions(self, content: str, file_path: str, budget: int) -> List[ContextSnippet]:
        """Extract function/class definitions from content."""
        snippets = []
        lines = content.split('\n')
        
        # Simple pattern: look for def/class/async def at start of line
        pattern = r'^(class|def|async\s+def)\s+(\w+)'
        
        for i, line in enumerate(lines):
            if re.match(pattern, line):
                # Estimate snippet is ~10-30 lines
                end = min(i + 20, len(lines))
                snippet_text = '\n'.join(lines[i:end])
                
                snippet = ContextSnippet(
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=end + 1,
                    content=snippet_text,
                    reason="function_definition"
                )
                
                if self._estimate_tokens(snippet) < budget:
                    snippets.append(snippet)
                    budget -= self._estimate_tokens(snippet)
        
        return snippets
    
    def _get_full_files(
        self,
        changed_files: Set[str],
        available_files: Dict[str, str],
        budget: int,
    ) -> Dict[str, str]:
        """Include full file content for critical files (cost: 3000+ tokens)."""
        full_content = {}
        tokens_used = 0
        
        for file_path in sorted(changed_files):  # Deterministic order
            if file_path not in available_files:
                continue
            
            content = available_files[file_path]
            content_tokens = self._estimate_tokens(content)
            
            if tokens_used + content_tokens <= budget:
                full_content[file_path] = content
                tokens_used += content_tokens
        
        return full_content
    
    @staticmethod
    def _estimate_tokens(obj) -> int:
        """Rough token estimation: ~4 characters per token."""
        if isinstance(obj, dict):
            text = str(obj)
        elif isinstance(obj, list):
            text = '\n'.join(str(x) for x in obj)
        elif isinstance(obj, ContextSnippet):
            text = obj.content
        elif isinstance(obj, str):
            text = obj
        else:
            text = str(obj)
        
        return max(10, len(text) // 4)
    
    @staticmethod
    def _is_complex_task(task_type: str) -> bool:
        """Determine if task is complex enough to justify Tier 3."""
        complex_tasks = {"feature", "refactor", "review", "debug"}
        return task_type in complex_tasks
