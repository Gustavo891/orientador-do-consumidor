"""Teste rápido do servidor MCP próprio: lista primitivas e chama duas ferramentas."""
import asyncio
import os
from pathlib import Path

os.environ["FASTMCP_LOG_LEVEL"] = "WARNING"
from fastmcp import Client

SERVER = Path(__file__).resolve().parent.parent / "servers" / "cdc_server.py"


async def main() -> None:
    async with Client(SERVER) as client:
        print("ferramentas:", [t.name for t in await client.list_tools()])
        print("recursos:", [str(r.uri) for r in await client.list_resources()], [t.uri_template for t in await client.list_resource_templates()])
        print("prompts:", [p.name for p in await client.list_prompts()])
        result = await client.call_tool("ler_artigo", {"numero": "39"})
        print(result.content[0].text[:120])
        result = await client.call_tool("calcular_prazo", {"tipo": "arrependimento", "data_inicio": "2026-11-14", "data_referencia": "2026-11-21"})
        print(result.content[0].text[:160])


if __name__ == "__main__":
    asyncio.run(main())
