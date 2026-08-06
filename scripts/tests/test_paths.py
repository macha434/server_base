from server_base_cli import paths


def test_repo_root_contains_scripts_and_stacks_dirs():
    assert (paths.REPO_ROOT / "scripts").is_dir()
    assert (paths.REPO_ROOT / "stacks").is_dir()
    assert (paths.REPO_ROOT / "core").is_dir()


def test_stack_dir():
    assert paths.stack_dir("myapp") == paths.STACKS_DIR / "myapp"


def test_stack_compose_path():
    assert paths.stack_compose_path("myapp") == paths.STACKS_DIR / "myapp" / "docker-compose.yml"


def test_script_path():
    assert paths.script_path("up.sh") == paths.SCRIPTS_DIR / "up.sh"


def test_compose_generated_path():
    assert paths.COMPOSE_GENERATED == paths.REPO_ROOT / "compose.generated.yaml"
