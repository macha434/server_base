# server_base

ローカルリポジトリを管理するためのベースサーバー

## 概要

このプロジェクトは、ローカルのGitリポジトリを紐づけて管理するための基本的なサーバーインフラを提供します。

## 機能

- ローカルリポジトリのパスを登録
- 登録されたリポジトリの一覧表示
- リポジトリ情報の取得
- リポジトリの登録解除

## 使用方法

### リポジトリの紐づけ

```bash
python repository_manager.py add /path/to/your/repository
```

### 紐づけられたリポジトリの一覧表示

```bash
python repository_manager.py list
```

### リポジトリ情報の取得

```bash
python repository_manager.py info /path/to/your/repository
```

### リポジトリの紐づけ解除

```bash
python repository_manager.py remove /path/to/your/repository
```

## 設定ファイル

設定は `config.json` に保存されます。初回使用時は自動的に作成されます。

手動で作成する場合は、`config.json.example` をコピーして使用してください：

```bash
cp config.json.example config.json
```

設定ファイルの形式：

```json
{
  "repositories": {
    "local_paths": []
  },
  "server": {
    "host": "localhost",
    "port": 8080
  }
}
```

## 要件

- Python 3.6以上

## サンプル使用例

```bash
# リポジトリを追加
$ python repository_manager.py add /home/user/my-project
Successfully linked repository: /home/user/my-project

# リポジトリ一覧を表示
$ python repository_manager.py list
Linked repositories:
  - /home/user/my-project

# リポジトリ情報を取得
$ python repository_manager.py info /home/user/my-project
{
  "path": "/home/user/my-project",
  "exists": true,
  "is_git": true
}

# リポジトリを削除
$ python repository_manager.py remove /home/user/my-project
Successfully unlinked repository: /home/user/my-project
```