from notion_client import Client
from notion.client import NotionClient as OldClient


class NotionClient:
    def __init__(self, token):
        if not token:
            raise ValueError("Notion API token must be provided")
        self._client = Client(auth=token)
        self._other = OldClient(token_v2=token)

    def get_page(self, page_id) -> dict:
        return self._client.pages.retrieve(page_id)

    def get_children(self, block_id) -> list:
        return self._client.blocks.children.list(block_id)["results"]

    def create_page(self, parent_id, name):
        return self._client.pages.create(
            **{
                "parent": {
                    "page_id": parent_id,
                },
                "properties": {
                    "title": {
                        "title": [
                            {
                                "text": {
                                    "content": name,
                                }
                            }
                        ]
                    },
                },
            }
        )

    def clear_page(self, page_id):
        children = self.get_children(page_id)
        for child in children:
            self._client.blocks.delete(child["id"])

    def delete_block(self, block_id):
        self._client.blocks.delete(block_id)

    def create_block(self, parent_id, block):
        return self._client.blocks.children.append(parent_id, children=[block])


class BlockFactory:
    def __init__(self):
        return

    def new_text_block(
        self,
        content,
        bold=False,
        italic=False,
        strikethrough=False,
        underline=False,
        code=False,
        color=None,
    ):
        return {
            "type": "text",
            "text": {
                "content": content,
            },
            "annotations": {
                "bold": bold,
                "italic": italic,
                "strikethrough": strikethrough,
                "underline": underline,
                "code": code,
                "color": color or "default",
            },
        }
