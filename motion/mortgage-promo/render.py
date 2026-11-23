#!/usr/bin/env python3
"""Render the approved 15-second scene, or encode captured browser frames.

Serve the repository over HTTP before using --url. The original product-motion
renderer uses file://; this scene needs same-origin fetch for the real prototype.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess


def encode(frames, out):
    paths = sorted(Path(frames).glob('*.jpg'))
    if len(paths) != 450:
        raise SystemExit(f'Expected 450 captured frames, got {len(paths)}')
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-framerate', '30', '-start_number', '0',
        '-i', str(Path(frames) / '%06d.jpg'),
        '-vf', 'scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-maxrate', '8M', '-bufsize', '16M', '-an',
        '-color_range', 'tv', '-colorspace', 'bt709',
        '-color_primaries', 'bt709', '-color_trc', 'bt709',
        '-movflags', '+faststart', '-frames:v', '450', str(out)
    ], check=True)
    if out.stat().st_size > 20_000_000:
        raise SystemExit(f'MP4 exceeds 20 MB: {out.stat().st_size} bytes')
    print(json.dumps({'file': str(out), 'bytes': out.stat().st_size,
                      'duration': 15, 'fps': 30, 'audio': False}, ensure_ascii=False))


def capture(url, frames):
    from playwright.sync_api import sync_playwright
    frames = Path(frames)
    frames.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--force-color-profile=srgb', '--hide-scrollbars'])
        page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(url)
        page.wait_for_function('window.READY===true')
        page.evaluate('document.fonts.ready')
        for i in range(450):
            page.evaluate('(t)=>window.render(t)', i / 30)
            page.screenshot(path=str(frames / f'{i:06d}.jpg'), type='jpeg', quality=95)
            if i % 90 == 0:
                print(f'{i}/450 frames', flush=True)
        browser.close()
        if errors:
            raise SystemExit('\n'.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url')
    parser.add_argument('--frames', default='build/frames')
    parser.add_argument('--out', default='out/mortgage-promo_16x9.mp4')
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parent)
    if args.url:
        capture(args.url, args.frames)
    encode(args.frames, args.out)


if __name__ == '__main__':
    main()
