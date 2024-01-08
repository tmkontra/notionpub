import argparse
from collections import UserDict, defaultdict
from collections.abc import Mapping
import os
import pathlib
import pprint
import re
from typing import Generator, Iterator
from notion.block import Block, Children, EmbedOrUploadBlock, ImageBlock


from notionpub import config, notion
from md2notion.upload import (
    convert,
    relativePathForMarkdownUrl,
    uploadBlock as md_upload_block,
)


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


def paragraph_to_blocks(children, image_handler):
    rich_text, images = [], []

    def text_to_block(t):
        print(t)
        if isinstance(t, str):
            return {"type": "text", "text": {"content": t}}
        elif issubclass(t["type"], EmbedOrUploadBlock):
            # always assumes external file url
            return image_handler(t)
        else:
            return notion.BlockFactory().new_text_block(
                t["title"],
                **{
                    "bold": t.get("_strong", False),
                    "italic": t.get("_emphasis", False),
                    "strikethrough": t.get("_strikethrough", False),
                    "underline": t.get("_underline", False),
                    "code": t.get("_code", False),
                    "color": "default",
                },
            )

    for child in children:
        b = text_to_block(child)
        if b is None:
            continue
        elif b["type"] == "text":
            rich_text.append(b)
        elif b["type"] == "image":
            images.append(b)
        else:
            raise ValueError("unsupported paragraph child: " + b["type"])
    return {"rich_text": rich_text, "children": images}


class ChildrenAdapter:
    def __init__(self, parent_id, client: notion.NotionClient) -> None:
        self._parent_id = parent_id
        self._client = client
        self._blocks = []

    def image_handler(self, image_block):
        if image_block["source"].startswith("http"):
            return {
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": image_block["source"]},
                },
            }
        else:
            return notion.BlockFactory().new_text_block(
                "Image {} was not uploaded".format(image_block["source"]),
                color="red",
            )

    def add_new(self, block_type, child_list_key=None, **kwargs):
        """
        Create a new block, add it as the last child of this parent block, and return the corresponding Block instance.
        `block_type` can be either a type string, or a Block subclass.
        """

        # determine the block type string from the Block class, if that's what was provided
        if (
            isinstance(block_type, type)
            and issubclass(block_type, Block)
            and hasattr(block_type, "_type")
        ):
            block_type = block_type._type
        elif not isinstance(block_type, str):
            raise Exception(
                "block_type must be a string or a Block subclass with a _type attribute"
            )

        headers = {
            "header": "heading_1",
            "sub_header": "heading_2",
            "sub_sub_header": "heading_3",
        }

        block_factory = notion.BlockFactory()
        if block_type in headers.keys():
            block_type = headers[block_type]
            block_content = {
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [block_factory.new_text_block(kwargs["title"])]
                },
            }
        elif block_type == "text":
            block_type = "paragraph"
            block_content = {
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [block_factory.new_text_block(kwargs["title"])]
                },
            }
        elif block_type == "bulleted_list":
            block_type = "bulleted_list_item"
            block_content = {
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [block_factory.new_text_block(kwargs["title"])]
                },
            }
        elif block_type == "paragraph":
            block_content = {
                "object": "block",
                "type": block_type,
                block_type: paragraph_to_blocks(
                    kwargs["rich_text"], self.image_handler
                ),
            }
        elif block_type == "numbered_list":
            block_type = "numbered_list_item"
            block_content = {
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [block_factory.new_text_block(kwargs["title"])]
                },
            }
        else:
            block_content = {
                "object": "block",
                "type": block_type,
                block_type: kwargs,
            }
            print(block_content)
            raise ValueError("unsupported block " + block_type)

        response = self._client.create_block(
            parent_id=self._parent_id, block=block_content
        )
        if "id" in response:
            return PageAdapter(response, self._client)
        if "results" in response:
            return PageAdapter(response["results"][0], self._client)
        print("other response", response)
        return response


class PageAdapter(UserDict):
    def __init__(self, page, client):
        self.page = page
        self.children = ChildrenAdapter(page["id"], client)
        super().__init__(page)


def _upload(dir: str, cfg: config.ConfigFile):
    dir = pathlib.Path(dir)
    files = _glob(cfg.paths, dir)
    client = notion.NotionClient(os.getenv("NOTION_INTEGRATION_SECRET"))
    dirs, files = _tree(files)
    parent = client.get_page(cfg.root_page_id)
    dir_pages = {}
    for dirname, subdir in dirs.items():
        _upload_dir(client, parent, dirname, subdir, [], dir_pages)
    for parent_parts, filepaths in files.items():
        for filepath in filepaths:
            parent_page_id = dir_pages[parent_parts]["id"]
            child_pages = [
                c
                for c in client.get_children(parent_page_id)
                if c["type"] == "child_page"
            ]
            try:
                target_page = next(
                    filter(
                        lambda p: p["child_page"]["title"] == filepath.name, child_pages
                    )
                )
                client.delete_block(target_page["id"])
            except StopIteration:
                continue
            target_page = client.create_page(parent_page_id, filepath.name)
            with open(dir / filepath, "r") as f:
                target_page = PageAdapter(target_page, client)
                for block in convert(f):
                    md_upload_block(block, target_page, dir / filepath)


def _upload_dir(client: notion.NotionClient, parent, dirname, subdir, parts, dir_pages):
    child_pages = [
        c for c in client.get_children(parent["id"]) if c["type"] == "child_page"
    ]
    try:
        dir_page = next(
            filter(lambda p: p["child_page"]["title"] == dirname, child_pages)
        )
    except StopIteration:
        dir_page = client.create_page(parent["id"], dirname)
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
        files[p.parent.parts].append(p)
    return trie, files


if __name__ == "__main__":
    main()
