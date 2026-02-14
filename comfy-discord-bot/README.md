# ComfyUI Discord Bot

A simple Discord bot that triggers image generation on a remote ComfyUI server (via Tailscale) and sends the generated image back to Discord.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export DISCORD_BOT_TOKEN=your_bot_token
export COMFY_HOST=http://lucapc.tail932dcc.ts.net:8000
export COMFY_CLIENT_ID=your_discord_client_id  # optional, for mention filtering
```

3. Run:
```bash
python bot.py
```

## Usage

In Discord, mention the bot or use the command:

```
!gen a beautiful sunset over the ocean
```

The bot will:
1. Queue the prompt on your remote ComfyUI server
2. Wait for the image to finish
3. Send the generated image back to the channel

## Commands

- `!gen <prompt>` - Generate an image with the given prompt
- `!queue` - Show current queue status on ComfyUI
- `!models` - List available checkpoint models

## Architecture

- Connects to ComfyUI via REST API
- Polls for completion (simple approach)
- Supports custom workflows via `workflows/` folder
