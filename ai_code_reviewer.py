#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
import requests

# --- Configuration ---
SUPPORTED_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
    '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.html', '.css',
    '.scss', '.sass', '.json', '.yaml', '.yml', '.md', '.sh', '.bash', '.sql'
}

EXCLUDE_DIRS = {
    '__pycache__', 'node_modules', 'venv', 'env', '.git', '.svn', '.hg',
    'dist', 'build', 'target', 'out', 'bin', 'obj', '.idea', '.vscode',
    '.DS_Store', 'Thumbs.db'
}

MAX_TOTAL_CHARS = 100_000  # Adjust based on LLM context limits (~100k chars ~ 25k tokens)

# --- Helper Functions ---
def clone_repo(repo_url: str, clone_dir: Path):
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    print(f"Cloning {repo_url} into {clone_dir}...")
    subprocess.run(['git', 'clone', '--depth=1', repo_url, str(clone_dir)], check=True)

def collect_code_files(root: Path):
    code_files = []
    for file_path in root.rglob('*'):
        if file_path.is_file():
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                rel_path = file_path.relative_to(root)
                parts = rel_path.parts
                if not any(part in EXCLUDE_DIRS for part in parts):
                    code_files.append(file_path)
    return sorted(code_files)

def read_file_safe(file_path: Path) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"[ERROR reading file: {e}]"

def build_prompt(code_snippets: list, repo_url: str) -> str:
    intro = (
        f"You are an expert software engineer performing a professional code review "
        f"for the GitHub repository: {repo_url}\n\n"
        f"Review the following code files. Focus on:\n"
        f"- Code quality, readability, and maintainability\n"
        f"- Potential bugs or security issues\n"
        f"- Performance concerns\n"
        f"- Adherence to best practices\n"
        f"- Suggestions for improvement (be specific and constructive)\n\n"
        f"Provide your feedback in the following format:\n\n"
        f"## Summary\n"
        f"<Brief overall assessment>\n\n"
        f"## Findings\n"
        f"- [Severity: High/Medium/Low] in `filename`: <description>\n"
        f"- ...\n\n"
        f"## Recommendations\n"
        f"<General advice for the project>\n\n"
        f"---\n\n"
    )

    file_blocks = []
    total_chars = len(intro)
    
    for file_path, content in code_snippets:
        block = f"### {file_path}\n\n```{file_path.suffix[1:]}\n{content}\n```\n\n"
        if total_chars + len(block) > MAX_TOTAL_CHARS:
            break
        file_blocks.append(block)
        total_chars += len(block)
    
    return intro + ''.join(file_blocks)

def get_code_review(prompt: str, api_key: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/lemon085",  # Replace with your actual URL if deployed
        "X-Title": "AI Code Reviewer",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-4o",  # Or use "anthropic/claude-3.5-sonnet" etc.
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 2000
    }
    print("Sending code to LLM for review...")
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")
    return response.json()['choices'][0]['message']['content']

def main():
    parser = argparse.ArgumentParser(description="AI Code Reviewer using OpenRouter")
    parser.add_argument("--repo", required=True, help="GitHub repository URL (e.g., https://github.com/user/repo.git)")
    parser.add_argument("--api-key", required=True, help="Your OpenRouter API key")
    parser.add_argument("--output", default="code_review_report.md", help="Output report file (default: code_review_report.md)")
    args = parser.parse_args()

    repo_url = args.repo
    api_key = args.api_key
    output_file = Path(args.output)

    clone_dir = Path("temp_repo_clone")
    try:
        clone_repo(repo_url, clone_dir)
        code_files = collect_code_files(clone_dir)
        
        if not code_files:
            print("No supported code files found in the repository!")
            return

        print(f"Found {len(code_files)} code files. Reading content...")
        snippets = []
        for f in code_files:
            content = read_file_safe(f)
            snippets.append((f.relative_to(clone_dir), content))

        prompt = build_prompt(snippets, repo_url)
        review = get_code_review(prompt, api_key)

        output_file.write_text(review, encoding='utf-8')
        print(f"\n✅ Code review report saved to: {output_file.resolve()}")

    finally:
        if clone_dir.exists():
            shutil.rmtree(clone_dir)

if __name__ == "__main__":
    main()
