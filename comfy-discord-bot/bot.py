#!/usr/bin/env python3
"""
ComfyUI Discord Bot
Triggers image generation on remote ComfyUI server and sends results back to Discord.
"""

import os
import asyncio
import aiohttp
import discord
from discord import app_commands
import uuid
import json
import time

# Config from environment
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
COMFY_HOST = os.getenv("COMFY_HOST", "http://lucapc.tail932dcc.ts.net:8000")
CLIENT_ID = os.getenv("COMFY_CLIENT_ID")

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Track active generations
generations = {}


async def queue_comfy_prompt(prompt: str, workflow: str = "default") -> str:
    """Queue a prompt on ComfyUI and return the prompt_id."""
    # Load workflow template
    workflow_path = f"workflows/{workflow}.json"
    if not os.path.exists(workflow_path):
        # Use default simple prompt workflow
        workflow_data = {
            "3": {"inputs": {"seed": int(time.time() * 1000) % 1000000000000, "steps": 20, "cfg": 8, "sampler_name": "euler", "scheduler": "normal", "positive": prompt, "negative": "", "model": ["4", 0], "clip": ["6", 0], "vae": ["7", 0]}, "class_type": "KSampler"},
            "4": {"inputs": {"ckpt_name": "sd15_default.json"}, "class_type": "CheckpointLoaderSimple"},
            "6": {"inputs": {"text": "", "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
            "7": {"inputs": {"vae_name": "vae-ft-mse-840000-ema-pruned.safetensors"}, "class_type": "VAELoader"},
            "8": {"inputs": {"width": 512, "height": 512, "batch_size": 1}, "class_type": "EmptyLatentImage"},
            "9": {"inputs": {"samples": ["3", 0], "vae": ["7", 0]}, "class_type": "VAEDecode"},
            "10": {"inputs": {"images": ["9", 0], "filename_prefix": "discord"}, "class_type": "SaveImage"}
        }
    else:
        with open(workflow_path) as f:
            workflow_data = json.load(f)
    
    # Replace prompt in workflow
    if "6" in workflow_data and "inputs" in workflow_data["6"]:
        workflow_data["6"]["inputs"]["text"] = prompt
    
    prompt_id = str(uuid.uuid4())
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{COMFY_HOST}/prompt", json={"prompt": workflow_data, "prompt_id": prompt_id}) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to queue prompt: {await resp.text()}")
            result = await resp.json()
            return result.get("prompt_id", prompt_id)


async def get_comfy_history(prompt_id: str) -> dict:
    """Get history for a prompt."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{COMFY_HOST}/history/{prompt_id}") as resp:
            if resp.status == 200:
                return await resp.json()
            return {}


async def get_comfy_queue() -> dict:
    """Get current queue status."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{COMFY_HOST}/queue") as resp:
            if resp.status == 200:
                return await resp.json()
            return {}


async def get_comfy_models() -> list:
    """Get available checkpoint models."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{COMFY_HOST}/object_info/CheckpointLoaderSimple") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("object_info", {}).get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [""],)
            return []


async def wait_for_comfy(prompt_id: str, timeout: int = 120) -> list:
    """Wait for generation to complete and return output images."""
    start = time.time()
    while time.time() - start < timeout:
        await asyncio.sleep(2)
        history = await get_comfy_history(prompt_id)
        if prompt_id in history:
            status = history[prompt_id].get("status", {})
            if status.get("completed", False):
                # Find output images
                outputs = history[prompt_id].get("outputs", {})
                images = []
                for node_id, node_data in outputs.items():
                    if "images" in node_data:
                        for img in node_data["images"]:
                            images.append({
                                "filename": img["filename"],
                                "subfolder": img.get("subfolder", ""),
                                "type": img.get("type", "output")
                            })
                return images
    return []


async def download_image(session: aiohttp.ClientSession, filename: str, subfolder: str = "", type: str = "output") -> bytes:
    """Download an image from ComfyUI."""
    params = {"filename": filename, "subfolder": subfolder, "type": type}
    async with session.get(f"{COMFY_HOST}/view", params=params) as resp:
        if resp.status == 200:
            return await resp.read()
        raise Exception(f"Failed to download image: {resp.status}")


@tree.command(name="gen", description="Generate an image with ComfyUI")
async def gen_command(interaction: discord.Interaction, *, prompt: str):
    """Generate an image from a text prompt."""
    await interaction.response.defer()
    
    try:
        # Queue the prompt
        prompt_id = await queue_comfy_prompt(prompt)
        
        # Tell user it's processing
        await interaction.followup.send(f"🎨 Generating: *{prompt}* (ID: {prompt_id[:8]}...)")
        
        # Wait for completion
        images = await wait_for_comfy(prompt_id)
        
        if not images:
            await interaction.followup.send("❌ Generation timed out or failed.")
            return
        
        # Download and send images
        async with aiohttp.ClientSession() as session:
            for img in images:
                img_data = await download_image(session, img["filename"], img["subfolder"], img["type"])
                file = discord.File(fp=io.BytesIO(img_data), filename=img["filename"])
                await interaction.followup.send(file=file)
                
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")


@tree.command(name="queue", description="Show ComfyUI queue status")
async def queue_command(interaction: discord.Interaction):
    """Show current queue status."""
    await interaction.response.defer()
    try:
        queue = await get_comfy_queue()
        await interaction.followup.send(f"📋 Queue: {json.dumps(queue, indent=2)}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")


@tree.command(name="models", description="List available models")
async def models_command(interaction: discord.Interaction):
    """List available checkpoint models."""
    await interaction.response.defer()
    try:
        models = await get_comfy_models()
        if models:
            await interaction.followup.send("📦 Available models:\n" + "\n".join(f"- {m}" for m in models))
        else:
            await interaction.followup.send("No models found or ComfyUI unreachable.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")


@bot.event
async def on_ready():
    """Bot is ready."""
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guilds")
    await tree.sync()
    print("Commands synced")


# Simple message handler for !gen prefix
@bot.event
async def on_message(message):
    """Handle messages."""
    if message.author.bot:
        return
    
    content = message.content.strip()
    
    # Handle !gen prefix
    if content.startswith("!gen "):
        prompt = content[5:].strip()
        if prompt:
            # Queue generation
            try:
                prompt_id = await queue_comfy_prompt(prompt)
                await message.add_reaction("🎨")
                await message.reply(f"Queued! ID: `{prompt_id[:8]}...`")
                
                # Wait in background
                images = await wait_for_comfy(prompt_id)
                
                if images:
                    async with aiohttp.ClientSession() as session:
                        for img in images:
                            img_data = await download_image(session, img["filename"], img["subfolder"], img["type"])
                            file = discord.File(fp=io.BytesIO(img_data), filename=img["filename"])
                            await message.channel.send(file=file)
                else:
                    await message.channel.send("❌ Generation timed out")
            except Exception as e:
                await message.reply(f"❌ Error: {str(e)}")
    
    # Handle !queue
    elif content == "!queue":
        try:
            queue = await get_comfy_queue()
            await message.reply(f"📋 Queue: `{json.dumps(queue)}`")
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    import io
    if not DISCORD_TOKEN:
        print("Error: DISCORD_BOT_TOKEN not set")
        exit(1)
    bot.run(DISCORD_TOKEN)
