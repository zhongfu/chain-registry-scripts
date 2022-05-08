#!/usr/bin/env python3
import asyncio
import json

from pathlib import Path
from typing import Any

import aiohttp
import jsonschema

from cw20 import get_terra_cw20_tokens
from native import get_terra_native_tokens


IMAGE_URL_BASE = "https://raw.githubusercontent.com/cosmos/chain-registry/master/terra/images"

with open("../chain-registry/assetlist.schema.json", "r", encoding="utf-8") as schema_f:
    ASSETLIST_SCHEMA = json.load(schema_f)

SAVE_PATH = Path("gen")
(SAVE_PATH / "images").mkdir(parents=True, exist_ok=True)



async def download_images(tokens: dict[str, Any]):
    urls_paths = []

    async def download_and_save(url_path: tuple[str, Path]):
        url, path = url_path
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url) as resp:
                if resp.status != 200:
                    print(f"error downloading image at {url} to {path}")
                    return

                with open(path, "wb") as img_f:
                    img_f.write(await resp.read())

    for token in tokens:
        for image_type, image_url in token.get("logo_URIs", {}).items():
            filename = f"{token['symbol'].lower()}.{image_type}"
            path = SAVE_PATH / "images" / filename

            if not path.exists():
                urls_paths.append((image_url, path))

    await asyncio.gather(*map(download_and_save, urls_paths))


async def generate() -> dict[str, Any]:
    cw20_tokens, native_tokens = await asyncio.gather(get_terra_cw20_tokens(), get_terra_native_tokens())

    with open(SAVE_PATH / "cw20_tokens.json", "w", encoding="utf-8") as cw20_f:
        json.dump(cw20_tokens, cw20_f)

    with open(SAVE_PATH / "native_tokens.json", "w", encoding="utf-8") as native_f:
        json.dump(native_tokens, native_f)

    with open("../chain-registry/terra/assetlist.json", "r", encoding="utf-8") as assetlist_f:
        current_list = json.load(assetlist_f)

    current_tokens = {
        token["base"]: token
        for token in current_list["assets"]
    }

    assert len(current_tokens) == len(current_list["assets"]), "current list seems to have duplicate base denoms!"

    all_new_tokens = cw20_tokens + native_tokens

    await download_images(all_new_tokens)

    for token in all_new_tokens:
        new_logo_uris = {}
        for image_type, image_url in token.get("logo_URIs", {}).items():
            filename = f"{token['symbol'].lower()}.{image_type}"
            path = SAVE_PATH / "images" / filename

            if path.exists():
                new_logo_uris[image_type] = f"{IMAGE_URL_BASE}/{filename}"

        if not new_logo_uris:
            token.pop("logo_URIs", None)
        else:
            token["logo_URIs"] = new_logo_uris

        if token["base"] in current_tokens.keys():
            current_tokens[token["base"]].update(token)
        else:
            current_tokens[token["base"]] = token

    assetlist = {
        "$schema": "../assetlist.schema.json",
        "chain_name": "terra",
        "assets": list(current_tokens.values())
    }

    with open(SAVE_PATH / "assetlist.json", "w", encoding="utf-8") as assetlist_f:
        json.dump(assetlist, assetlist_f, indent=2)

    jsonschema.validate(assetlist, ASSETLIST_SCHEMA)


if __name__ == '__main__':
    asyncio.run(generate())
