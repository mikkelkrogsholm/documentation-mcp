"""CLI entry point for documentation fetcher."""

import argparse
from pathlib import Path

from src.modules.gemini.module import GeminiModule
from src.modules.fastmcp.module import FastMCPModule
from src.modules.claudecode.module import ClaudeCodeModule
from src.modules.betterauth.module import BetterAuthModule
from src.modules.drizzle.module import DrizzleModule
from src.modules.nextintl.module import NextIntlModule
from src.modules.resend.module import ResendModule
from src.modules.reactemail.module import ReactEmailModule
from src.modules.shadcn.module import ShadcnModule
from src.modules.stripe.module import StripeModule
from src.modules.nextjs.module import NextjsModule
from src.modules.svelte.module import SvelteModule
from src.rag.search import search


def fetch_command(args):
    """Handle the fetch subcommand."""
    # Determine output directory
    output_dir = args.output or Path("output") / args.module

    # Run the appropriate module
    if args.module == "gemini":
        module = GeminiModule()
        module.run(output_dir)
    elif args.module == "fastmcp":
        module = FastMCPModule()
        module.run(output_dir)
    elif args.module == "claudecode":
        module = ClaudeCodeModule()
        module.run(output_dir)
    elif args.module == "betterauth":
        module = BetterAuthModule()
        module.run(output_dir)
    elif args.module == "drizzle":
        module = DrizzleModule()
        module.run(output_dir)
    elif args.module == "nextintl":
        module = NextIntlModule()
        module.run(output_dir)
    elif args.module == "resend":
        module = ResendModule()
        module.run(output_dir)
    elif args.module == "reactemail":
        module = ReactEmailModule()
        module.run(output_dir)
    elif args.module == "shadcn":
        module = ShadcnModule()
        module.run(output_dir)
    elif args.module == "stripe":
        module = StripeModule()
        module.run(output_dir)
    elif args.module == "nextjs":
        module = NextjsModule()
        module.run(output_dir)
    elif args.module == "svelte":
        module = SvelteModule()
        module.run(output_dir)


def search_command(args):
    """Handle the search subcommand."""
    # Perform search
    try:
        # Determine feature flags (enabled by default)
        use_rerank = not args.no_rerank
        use_expand = not args.no_expand

        # Show search mode
        mode_parts = []
        if use_expand:
            mode_parts.append("query expansion")
        if use_rerank:
            mode_parts.append("reranking")
        if mode_parts:
            print(f"Search mode: {' + '.join(mode_parts)}")

        results = search(
            query=args.query,
            top_k=args.top_k,
            collection=args.collection,
            rerank=use_rerank,
            expand_query=use_expand
        )

        if not results:
            print("No results found.")
            return

        # Display results
        print(f"\nResults for: \"{args.query}\"\n")

        for i, result in enumerate(results, 1):
            # Print header
            print(f"[{i}] {result.section or 'Untitled'} (score: {result.score:.3f})")
            print(f"    Source: {result.source_url}")

            # Print rank information if verbose
            if args.verbose:
                ranks = []
                if result.semantic_rank:
                    ranks.append(f"semantic={result.semantic_rank}")
                if result.keyword_rank:
                    ranks.append(f"keyword={result.keyword_rank}")
                if ranks:
                    print(f"    Ranks: {', '.join(ranks)}")

            # Print separator
            print("    ---")

            # Print full chunk content
            print(f"    {result.content}")
            print()

    except Exception as e:
        print(f"Error during search: {e}")
        import sys
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Documentation fetcher and RAG search system",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Fetch subcommand
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch API documentation in markdown format"
    )
    fetch_parser.add_argument(
        "module",
        choices=["gemini", "fastmcp", "claudecode", "betterauth", "drizzle", "nextintl", "resend", "reactemail", "shadcn", "stripe", "nextjs", "svelte"],
        help="Documentation module to run"
    )
    fetch_parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output directory (default: output/<module>)"
    )
    fetch_parser.set_defaults(func=fetch_command)

    # Search subcommand
    search_parser = subparsers.add_parser(
        "search",
        help="Search indexed documentation using RAG"
    )
    search_parser.add_argument(
        "query",
        help="Search query string"
    )
    search_parser.add_argument(
        "-n", "--top-k",
        type=int,
        default=5,
        dest="top_k",
        help="Number of results to return (default: 5)"
    )
    search_parser.add_argument(
        "-c", "--collection",
        default="gemini",
        help="Collection to search (default: gemini)"
    )
    search_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output including ranks"
    )
    search_parser.add_argument(
        "--no-rerank",
        action="store_true",
        dest="no_rerank",
        help="Disable cross-encoder reranking (enabled by default)"
    )
    search_parser.add_argument(
        "--no-expand",
        action="store_true",
        dest="no_expand",
        help="Disable multi-query expansion (enabled by default)"
    )
    search_parser.set_defaults(func=search_command)

    # Parse arguments
    args = parser.parse_args()

    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return

    # Execute the appropriate command
    args.func(args)


if __name__ == "__main__":
    main()
