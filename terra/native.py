#!/usr/bin/env python3
import asyncio

from typing import Any

import aiohttp


TERRA_TOKEN_IMAGE_PNG_URL_BASE = "https://github.com/terra-money/assets/raw/master/icon/600"
TERRA_TOKEN_IMAGE_SVG_URL_BASE = "https://github.com/terra-money/assets/raw/master/icon/svg"

TERRA_FCD_URL = "https://fcd.terra.dev"

TERRA_NATIVE_TOKEN_METADATA_URL = f"{TERRA_FCD_URL}/cosmos/bank/v1beta1/denoms_metadata"


def get_image_url(symbol: str, filetype: str) -> str:
    assert filetype in ("svg", "png"), f"invalid filetype {filetype}"

    if symbol == "LUNA":
        path_part = "Luna"
    else:
        if filetype == "svg":
            path_part = f"Terra/{symbol}"
        else:
            path_part = symbol

    if filetype == "png":
        return f"{TERRA_TOKEN_IMAGE_PNG_URL_BASE}/{path_part}.{filetype}"
    else: # svg
        return f"{TERRA_TOKEN_IMAGE_SVG_URL_BASE}/{path_part}.{filetype}"


async def generate_terra_native_asset_dict(token_raw: dict[str, Any]) -> dict[str, Any]:
    """
    tidies up data, e.g.:
    - names: "USD TERRA" -> "TerraUSD", "LUNA" -> "Luna"
    - description: for stablecoins, "The USD stablecoin of Terra."; for others, "of the Terra Columbus." -> "of Terra."
    - icons: adds icons
    """
    token = token_raw.copy()

    is_stablecoin = token["name"].endswith(" TERRA")
    if is_stablecoin:
        actual_currency_symbol = token["name"].split(" ", 1)[0]
        token["name"] = f"Terra{token['symbol']}"
    elif token["name"] == "LUNA":
        token["name"] = "Luna"

    if is_stablecoin:
        token["description"] = f"The {actual_currency_symbol} stablecoin of Terra."
    else:
        token["description"] = token["description"].replace(" of the Terra Columbus.", " of Terra.")

    token["logo_URIs"] = {
        "svg": get_image_url(token["symbol"], "svg"),
        "png": get_image_url(token["symbol"], "png")
    }

    return token


async def get_terra_native_tokens() -> list[str, Any]:
    """
    returns a list of an asset dicts compliant with the cosmos/chain-registry assetlist json schema
    """
    async with aiohttp.ClientSession() as sess:
        async with sess.get(TERRA_NATIVE_TOKEN_METADATA_URL) as resp:
            assert resp.status == 200, f"got invalid response code {resp.status} while getting terra native token manifest"

            resp_json = await resp.json()
            assert resp_json["pagination"]["next_key"] is None, "Got too many results, and pagination is not implemented"

            tokens = resp_json["metadatas"]

    tokens_aws = asyncio.gather(*map(generate_terra_native_asset_dict, tokens))

    tokens = await tokens_aws

    token_bases = set(token["base"] for token in tokens)
    assert len(tokens) == len(token_bases), f"Got {len(tokens)} tokens, but only {len(token_bases)} unique base denoms!"

    return tokens
