#!/bin/bash
# Script to setup GitHub repository and push code

REPO_NAME="guardrail"
GITHUB_USERNAME=""  # Set your GitHub username here

echo "=========================================="
echo "GitHub Repository Setup"
echo "=========================================="
echo ""
echo "Step 1: Create a new repository on GitHub"
echo "  1. Go to https://github.com/new"
echo "  2. Repository name: $REPO_NAME (or your preferred name)"
echo "  3. Set visibility (Public/Private)"
echo "  4. DO NOT initialize with README, .gitignore, or license"
echo "  5. Click 'Create repository'"
echo ""
read -p "Enter your GitHub username: " GITHUB_USERNAME
read -p "Enter repository name (default: guardrail): " REPO_NAME_INPUT

if [ ! -z "$REPO_NAME_INPUT" ]; then
    REPO_NAME=$REPO_NAME_INPUT
fi

echo ""
echo "Adding remote origin..."
git remote add origin https://github.com/$GITHUB_USERNAME/$REPO_NAME.git 2>/dev/null || \
git remote set-url origin https://github.com/$GITHUB_USERNAME/$REPO_NAME.git

echo "Pushing to main branch..."
git push -u origin main

echo ""
echo "=========================================="
echo "Done! Your code is now on GitHub:"
echo "https://github.com/$GITHUB_USERNAME/$REPO_NAME"
echo "=========================================="

