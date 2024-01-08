# notionpub

This utility uploads markdown files to a Notion workspace.

:construction: It is currently a frankenstein wrapper of [md2notion](https://github.com/Cobertos/md2notion) and [notion-py](https://github.com/jamalex/notion-py) which are two abandoned projects. 

md2notion implements a markdown to Notion block mapping -- but the published code is outdated and now incompatible with the public Notion API. 

notion-py is a python client that appears to use the non-public Notion API -- but it also implements an object model for Notion blocks, which is very helpful for passing around and transforming blocks.

notionpub uses [notion-sdk-py](https://github.com/ramnes/notion-sdk-py) as its API client.


# :warning: Major Limitations

- Images from the filesystem are not uploaded 
  - Currently, the Notion API does not support this: https://developers.notion.com/reference/file-object
- An upload will first delete any existing pages, before re-creating them and populating them with content
  - This prevents viewing page history in Notion


# Usage

This project is currently in pre-alpha, but if you manage to download and install it, you can run it like so:

```sh
export NOTION_INTEGRATION_SECRET=secret_xyz123
python -m notionpub.main upload ./my/directory/ -c notionpub.yaml
```

# TODO :wrench:

- [ ] support configuring "delete-and-recreate" vs "clear page and repopulate"
- support remaining blocks 
  - [ ] CodeBlock
  - [ ] DividerBlock
  - [x] HeaderBlock
  - [x] ParagraphBlock
  - [x] SubheaderBlock
  - [x] SubsubheaderBlock
  - [ ] QuoteBlock
  - [x] TextBlock
  - [x] NumberedListBlock
  - [x] BulletedListBlock
  - [x] ImageBlock
  - [ ] CollectionViewBlock
  - [ ] TodoBlock
  - [ ] EquationBlock
- [ ] implement "bulk block append"
  - at the page level, we should build up the full list of child blocks and "append" them all at once
  - this is tricky because those children may themselves have children, and the parent needs to exist before the children can be uploaded, so a fully-recursive implementation where the "deepest" block is uploaded first, is not possible 
  - I suppose this will require some sort of "breadth-first" algorithm, where we build up the first-level child list, upload them all at once, then do the same for each child once we have their `id` from the api.