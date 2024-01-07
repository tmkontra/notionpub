import argparse
from collections import defaultdict
import os
import pathlib
import pprint
from typing import Generator, Iterator

import md2notion.upload

from notionpub import config, notion


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest="subcommand")
upload = subparsers.add_parser("upload")

upload.add_argument("directory")
upload.add_argument("--config", "-c", required=False, default="notionpub.yaml")


def main():
    args = parser.parse_args()
    if args.subcommand == "upload":
        with open(args.config, "r") as f:
            cfg = config.load_config(f)
        _upload(args.directory, cfg)


def _upload(dir: str, cfg: config.ConfigFile):
    dir = pathlib.Path(dir)
    files = _glob(cfg.paths, dir)
    client = notion.NotionClient(os.getenv("NOTION_INTEGRATION_SECRET"))
    dirs, files = _tree(files)
    parent = client.get_page(cfg.root_page_id)
    dir_pages = {}
    for dirname, subdir in dirs.items():
        _upload_dir(client, parent, dirname, subdir, [], dir_pages)
    for parent_parts, filepath in files.items():
        parent_page_id = dir_pages[parent_parts]["id"]
        child_pages = [c for c in client.get_children(parent_page_id)
                       if c['type'] == "child_page"]
        try:
            target_page = next(
                filter(lambda p: p["child_page"]["title"] == filepath.name, child_pages))
            client.clear_page(target_page['id'])
        except StopIteration:
            target_page = client.create_page(parent['id'], filepath.name)
        with open(dir / filepath, "r") as f:
            md_page = client.get_md_page(target_page["id"])
            md2notion.upload.upload(f, md_page)


def _upload_dir(
        client: notion.NotionClient,
        parent, dirname, subdir,
        parts, dir_pages):
    child_pages = [c for c in client.get_children(parent["id"])
                   if c['type'] == "child_page"]
    try:
        dir_page = next(
            filter(lambda p: p["child_page"]["title"] == dirname, child_pages))
    except StopIteration:
        dir_page = client.create_page(parent['id'], dirname)
    p = parts + [dirname]
    dir_pages[tuple(p)] = dir_page
    for dirname, subdir in subdir.items():
        _upload_dir(client, dir_page, dirname, subdir, p, dir_pages)


def _glob(paths, root):
    for pattern in paths:
        _, ext = os.path.splitext(pattern)
        if not ext:
            if pattern.endswith("**"):
                pattern += "/*"
            pattern += ".md"
        for p in root.glob(pattern):
            yield p.relative_to(root)


def _tree(paths: Iterator[pathlib.PurePath]):
    nested_dict = lambda: defaultdict(nested_dict)
    trie = nested_dict()
    files = defaultdict(list)
    for p in paths:
        sub = trie
        for part in p.parent.parts:
            sub = sub[part]
        files[p.parent.parts] = p
    return trie, files


if __name__ == "__main__":
    main()
