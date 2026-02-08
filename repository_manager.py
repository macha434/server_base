#!/usr/bin/env python3
"""
Repository Manager - Manages linked local repositories
"""
import json
import os
from pathlib import Path
from typing import List, Dict


class RepositoryManager:
    """Manages local repository links"""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize the repository manager with a config file"""
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from JSON file"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {"repositories": {"local_paths": []}, "server": {"host": "localhost", "port": 8080}}
    
    def _save_config(self):
        """Save configuration to JSON file"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def add_repository(self, path: str) -> bool:
        """
        Add a local repository path
        
        Args:
            path: Local filesystem path to the repository
            
        Returns:
            True if added successfully, False otherwise
        """
        abs_path = os.path.abspath(path)
        
        # Verify path exists
        if not os.path.exists(abs_path):
            print(f"Error: Path does not exist: {abs_path}")
            return False
        
        # Verify it's a git repository
        if not os.path.isdir(os.path.join(abs_path, '.git')):
            print(f"Warning: Path is not a git repository: {abs_path}")
        
        # Check if already added
        if abs_path in self.config["repositories"]["local_paths"]:
            print(f"Repository already linked: {abs_path}")
            return False
        
        # Add to config
        self.config["repositories"]["local_paths"].append(abs_path)
        self._save_config()
        print(f"Successfully linked repository: {abs_path}")
        return True
    
    def remove_repository(self, path: str) -> bool:
        """
        Remove a local repository path
        
        Args:
            path: Local filesystem path to the repository
            
        Returns:
            True if removed successfully, False otherwise
        """
        abs_path = os.path.abspath(path)
        
        if abs_path in self.config["repositories"]["local_paths"]:
            self.config["repositories"]["local_paths"].remove(abs_path)
            self._save_config()
            print(f"Successfully unlinked repository: {abs_path}")
            return True
        
        print(f"Repository not found: {abs_path}")
        return False
    
    def list_repositories(self) -> List[str]:
        """
        List all linked repositories
        
        Returns:
            List of repository paths
        """
        return self.config["repositories"]["local_paths"]
    
    def get_repository_info(self, path: str) -> Dict:
        """
        Get information about a repository
        
        Args:
            path: Local filesystem path to the repository
            
        Returns:
            Dictionary containing repository information
        """
        abs_path = os.path.abspath(path)
        
        if abs_path not in self.config["repositories"]["local_paths"]:
            return {"error": "Repository not linked"}
        
        info = {
            "path": abs_path,
            "exists": os.path.exists(abs_path),
            "is_git": os.path.isdir(os.path.join(abs_path, '.git'))
        }
        
        return info


def main():
    """CLI interface for repository manager"""
    import sys
    
    manager = RepositoryManager()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python repository_manager.py add <path>     - Link a local repository")
        print("  python repository_manager.py remove <path>  - Unlink a repository")
        print("  python repository_manager.py list           - List all linked repositories")
        print("  python repository_manager.py info <path>    - Get repository information")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "add":
        if len(sys.argv) < 3:
            print("Error: Please provide a repository path")
            sys.exit(1)
        manager.add_repository(sys.argv[2])
    
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Error: Please provide a repository path")
            sys.exit(1)
        manager.remove_repository(sys.argv[2])
    
    elif command == "list":
        repos = manager.list_repositories()
        if repos:
            print("Linked repositories:")
            for repo in repos:
                print(f"  - {repo}")
        else:
            print("No repositories linked")
    
    elif command == "info":
        if len(sys.argv) < 3:
            print("Error: Please provide a repository path")
            sys.exit(1)
        info = manager.get_repository_info(sys.argv[2])
        print(json.dumps(info, indent=2))
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
