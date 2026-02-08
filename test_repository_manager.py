#!/usr/bin/env python3
"""
Tests for repository manager
"""
import json
import os
import tempfile
import shutil
from repository_manager import RepositoryManager


def test_add_repository():
    """Test adding a repository"""
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        manager = RepositoryManager(config_path)
        
        # Create a temporary git repository
        repo_dir = os.path.join(tmpdir, "test_repo")
        os.makedirs(repo_dir)
        os.makedirs(os.path.join(repo_dir, ".git"))
        
        # Add repository
        result = manager.add_repository(repo_dir)
        assert result, "Failed to add repository"
        
        # Verify it was added
        repos = manager.list_repositories()
        assert repo_dir in repos, "Repository not in list"
        
        print("✓ test_add_repository passed")


def test_list_repositories():
    """Test listing repositories"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        manager = RepositoryManager(config_path)
        
        # Create multiple test repositories
        repo1 = os.path.join(tmpdir, "repo1")
        repo2 = os.path.join(tmpdir, "repo2")
        
        for repo in [repo1, repo2]:
            os.makedirs(repo)
            os.makedirs(os.path.join(repo, ".git"))
            manager.add_repository(repo)
        
        # List repositories
        repos = manager.list_repositories()
        assert len(repos) == 2, f"Expected 2 repositories, got {len(repos)}"
        assert repo1 in repos, "repo1 not found"
        assert repo2 in repos, "repo2 not found"
        
        print("✓ test_list_repositories passed")


def test_remove_repository():
    """Test removing a repository"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        manager = RepositoryManager(config_path)
        
        # Create and add a repository
        repo_dir = os.path.join(tmpdir, "test_repo")
        os.makedirs(repo_dir)
        os.makedirs(os.path.join(repo_dir, ".git"))
        manager.add_repository(repo_dir)
        
        # Remove repository
        result = manager.remove_repository(repo_dir)
        assert result, "Failed to remove repository"
        
        # Verify it was removed
        repos = manager.list_repositories()
        assert repo_dir not in repos, "Repository still in list"
        
        print("✓ test_remove_repository passed")


def test_get_repository_info():
    """Test getting repository information"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        manager = RepositoryManager(config_path)
        
        # Create and add a repository
        repo_dir = os.path.join(tmpdir, "test_repo")
        os.makedirs(repo_dir)
        os.makedirs(os.path.join(repo_dir, ".git"))
        manager.add_repository(repo_dir)
        
        # Get repository info
        info = manager.get_repository_info(repo_dir)
        assert info["exists"], "Repository should exist"
        assert info["is_git"], "Repository should be a git repo"
        assert info["path"] == repo_dir, "Path mismatch"
        
        print("✓ test_get_repository_info passed")


def test_config_persistence():
    """Test that configuration persists to file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        
        # Create and add a repository
        repo_dir = os.path.join(tmpdir, "test_repo")
        os.makedirs(repo_dir)
        os.makedirs(os.path.join(repo_dir, ".git"))
        
        manager1 = RepositoryManager(config_path)
        manager1.add_repository(repo_dir)
        
        # Create a new manager instance with same config
        manager2 = RepositoryManager(config_path)
        repos = manager2.list_repositories()
        
        assert repo_dir in repos, "Configuration was not persisted"
        
        print("✓ test_config_persistence passed")


if __name__ == "__main__":
    print("Running repository manager tests...\n")
    
    test_add_repository()
    test_list_repositories()
    test_remove_repository()
    test_get_repository_info()
    test_config_persistence()
    
    print("\n✓ All tests passed!")
