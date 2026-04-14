from .registry import default_registry
from .branch_comparison import BranchComparisonTool

# Register initial tools
default_registry.register(BranchComparisonTool())
