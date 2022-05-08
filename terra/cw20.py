#!/usr/bin/env python3
import asyncio
import base64
import json # woo, two json libraries!!

from typing import Any

import aiohttp
import pyjson5


TERRA_CW20_TOKENS_JS_URL = "https://github.com/terra-money/assets/raw/master/cw20/tokens.js"

TERRA_LCD_URL = "https://lcd.terra.dev"


async def get_terra_cw20_info_from_chain(addr: str) -> dict[str, Any]:
    """
    returns:
    {
        "name": "...",
        "symbol": "...",
        "decimals": ...,
        "total_supply": "..."
    }
    plus any other returned attrs, if the token exists

    returns None if we get "not found" in the rpc response (token doesn't exist on network?)

    throws otherwise
    """

    query = {
        "token_info": {}
    }
    query_b64 = base64.b64encode(json.dumps(query).encode("ascii")).decode("ascii")

    params = {
        "query_msg": query_b64
    }

    async with aiohttp.ClientSession() as sess:
        async with sess.get(f"{TERRA_LCD_URL}/terra/wasm/v1beta1/contracts/{addr}/store", params=params) as resp:
            assert resp.status in (200, 500), f"got invalid response code {resp.status} while getting token info for {addr}"

            resp_json = await resp.json()

            if resp.status == 500:
                if "message" in resp_json and "not found: unknown request" in resp_json["message"]:
                    return None

                raise Exception(f"Got unexpected response '{resp_json}' while getting token info for {addr}")
            elif resp.status == 200:
                if "query_result" not in resp_json:
                    raise Exception(f"Got invalid query result while getting token info for {addr}")

                token_info = resp_json["query_result"]
                diff = set(("name", "symbol", "decimals", "total_supply")).difference(token_info.keys())
                if len(diff) > 0:
                    raise KeyError(f"Token info for {addr} is missing keys: {diff}")

                return token_info
            else:
                # we should never reach here
                raise Exception(f"Got invalid response code {resp.status} while getting token info for {addr}")


async def generate_terra_cw20_asset_dict(addr: str, token_raw: dict[str, Any]) -> dict[str, Any]:
    assert addr.startswith("terra1") and len(addr) == 44, f"got possibly invalid address {addr}"

    token_info = await get_terra_cw20_info_from_chain(addr)

    if not token_info:
        raise Exception(f"couldn't get token info for {addr}: addr doesn't exist on-chain")

    base = f"cw20:{addr}"
    display = token_raw["symbol"].lower()

    denom_units = [
        {
            "denom": base,
            "exponent": 0
        },
        {
            "denom": display,
            "exponent": token_info["decimals"]
        }
    ]

    name = token_raw["name"] if "name" in token_raw else token_info["name"]

    token = dict(
        denom_units=denom_units,
        type_asset="cw20",
        address=addr,
        base=base,
        name=name,
        display=display,
        symbol=token_raw["symbol"]
    )

    icon = token_raw["icon"]
    if icon.endswith(".svg"):
        token["logo_URIs"] = {
            "svg": icon
        }
    elif icon.endswith(".png"):
        token["logo_URIs"] = {
            "png": icon
        }

    return token


async def get_terra_cw20_tokens() -> list[dict[str, Any]]:
    """
    returns a list of an asset dicts compliant with the cosmos/chain-registry assetlist json schema
    """
    async with aiohttp.ClientSession() as sess:
        async with sess.get(TERRA_CW20_TOKENS_JS_URL) as resp:
            assert resp.status == 200, f"got invalid response code {resp.status} while getting terra cw20 token manifest"

            # nasty kludge but it'll work
            tokens_js_raw = (await resp.text()).removeprefix("module.exports = ")
            tokens_raw = pyjson5.loads(tokens_js_raw)['mainnet']

    tokens_aws = asyncio.gather(*map(lambda t: generate_terra_cw20_asset_dict(t[0], t[1]), tokens_raw.items()))

    tokens = await tokens_aws

    token_bases = set(token["base"] for token in tokens)
    assert len(tokens) == len(token_bases), f"Got {len(tokens)} tokens, but only {len(token_bases)} unique base denoms!"

    return tokens
