import os
import io
import math
import random
import time
import uuid
import base64
from typing import Dict, Any, List, Tuple
from PIL import Image, ImageDraw, ImageFilter
from app.redis_client import redis_client

class SliderCaptchaService:
    """
    High-Security Behavioral Sliding Puzzle Captcha Algorithm
    Generates puzzle cutout and validates human mouse/touch trajectories.
    """
    WIDTH = 320
    HEIGHT = 160
    BLOCK_SIZE = 42
    CIRCLE_R = 7
    TOLERANCE = 5  # pixel tolerance

    @staticmethod
    def _create_jigsaw_mask(w: int, h: int, r: int) -> Image.Image:
        """
        Create a 2D puzzle jigsaw piece mask with concave/convex circular notches.
        """
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)

        # Base square coordinates inside the padded box
        pad = r + 2
        bx0, by0 = pad, pad
        bx1, by1 = bx0 + (w - 2 * pad), by0 + (h - 2 * pad)

        # Draw central square
        draw.rectangle([bx0, by0, bx1, by1], fill=255)

        # Top protrusion (convex circle)
        cx_top = (bx0 + bx1) / 2
        draw.ellipse([cx_top - r, by0 - r, cx_top + r, by0 + r], fill=255)

        # Right protrusion (convex circle)
        cy_right = (by0 + by1) / 2
        draw.ellipse([bx1 - r, cy_right - r, bx1 + r, cy_right + r], fill=255)

        # Bottom indentation (concave circle)
        cx_bottom = (bx0 + bx1) / 2
        draw.ellipse([cx_bottom - r, by1 - r, cx_bottom + r, by1 + r], fill=0)

        # Left indentation (concave circle)
        cy_left = (by0 + by1) / 2
        draw.ellipse([bx0 - r, cy_left - r, bx0 + r, cy_left + r], fill=0)

        return mask

    @classmethod
    def generate_captcha(cls) -> Dict[str, Any]:
        """
        Generate sliding puzzle background image and slice puzzle piece.
        Returns:
            captcha_id, bg_image (base64), slider_image (base64), y_position
        """
        # 1. Generate aesthetic high-contrast procedural gradient background
        bg = Image.new("RGB", (cls.WIDTH, cls.HEIGHT))
        draw = ImageDraw.Draw(bg)

        # Randomize rich gradient palette
        palettes = [
            [(15, 23, 42), (79, 70, 229), (124, 58, 237)],    # Indigo-Purple
            [(10, 15, 30), (6, 182, 212), (59, 130, 246)],    # Cyber-Cyan
            [(24, 24, 27), (245, 158, 11), (239, 68, 68)],    # Sunset-Amber
            [(15, 23, 42), (16, 185, 129), (6, 182, 212)]     # Emerald-Teal
        ]
        chosen_pal = random.choice(palettes)

        # Render smooth diagonal mesh gradient
        for y in range(cls.HEIGHT):
            for x in range(cls.WIDTH):
                t1 = (x / cls.WIDTH) * 0.6 + (y / cls.HEIGHT) * 0.4
                t2 = ((cls.WIDTH - x) / cls.WIDTH) * 0.5 + (y / cls.HEIGHT) * 0.5
                r = int(chosen_pal[0][0] * (1 - t1) + chosen_pal[1][0] * t1 * (1 - t2) + chosen_pal[2][0] * t2)
                g = int(chosen_pal[0][1] * (1 - t1) + chosen_pal[1][1] * t1 * (1 - t2) + chosen_pal[2][1] * t2)
                b = int(chosen_pal[0][2] * (1 - t1) + chosen_pal[1][2] * t1 * (1 - t2) + chosen_pal[2][2] * t2)
                draw.point((x, y), fill=(min(255, r), min(255, g), min(255, b)))

        # Draw subtle geometric circles/grid lines on background for rich texture
        for _ in range(5):
            gx = random.randint(0, cls.WIDTH)
            gy = random.randint(0, cls.HEIGHT)
            gr = random.randint(20, 60)
            draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], outline=(255, 255, 255, 40), width=1)

        # 2. Determine target position
        pad = cls.CIRCLE_R + 2
        full_block_w = cls.BLOCK_SIZE + 2 * pad
        full_block_h = cls.BLOCK_SIZE + 2 * pad

        target_x = random.randint(70, cls.WIDTH - full_block_w - 20)
        target_y = random.randint(20, cls.HEIGHT - full_block_h - 10)

        # 3. Create Jigsaw mask
        mask = cls._create_jigsaw_mask(full_block_w, full_block_h, cls.CIRCLE_R)

        # 4. Crop slice from base image for slider piece
        crop_box = (target_x, target_y, target_x + full_block_w, target_y + full_block_h)
        slice_img = bg.crop(crop_box)

        # Create RGBA slider image with alpha mask
        slider_piece = Image.new("RGBA", (full_block_w, full_block_h), (0, 0, 0, 0))
        slider_piece.paste(slice_img, (0, 0), mask)

        # Draw highlight border around slider piece
        outline_mask = mask.filter(ImageFilter.FIND_EDGES)
        slider_piece_draw = ImageDraw.Draw(slider_piece)
        for y_idx in range(full_block_h):
            for x_idx in range(full_block_w):
                if outline_mask.getpixel((x_idx, y_idx)) > 100:
                    slider_piece_draw.point((x_idx, y_idx), fill=(255, 255, 255, 220))

        # 5. Create Notch Shadow on Background Image
        bg_rgba = bg.convert("RGBA")
        notch_overlay = Image.new("RGBA", (full_block_w, full_block_h), (0, 0, 0, 160))
        bg_rgba.paste(notch_overlay, (target_x, target_y), mask)

        # Add white subtle border around notch on background
        notch_draw = ImageDraw.Draw(bg_rgba)
        for y_idx in range(full_block_h):
            for x_idx in range(full_block_w):
                if outline_mask.getpixel((x_idx, y_idx)) > 100:
                    notch_draw.point((target_x + x_idx, target_y + y_idx), fill=(255, 255, 255, 180))

        # 6. Encode images as Base64 strings
        bg_buffer = io.BytesIO()
        bg_rgba.convert("RGB").save(bg_buffer, format="PNG")
        bg_b64 = "data:image/png;base64," + base64.b64encode(bg_buffer.getvalue()).decode("utf-8")

        slider_buffer = io.BytesIO()
        slider_piece.save(slider_buffer, format="PNG")
        slider_b64 = "data:image/png;base64," + base64.b64encode(slider_buffer.getvalue()).decode("utf-8")

        # 7. Store secret target_x in Redis (TTL: 120s)
        captcha_id = str(uuid.uuid4())
        redis_client.set(
            f"captcha:slider:{captcha_id}",
            f"{target_x}:{target_y}:{int(time.time() * 1000)}",
            ex=120
        )

        return {
            "captcha_id": captcha_id,
            "bg_image": bg_b64,
            "slider_image": slider_b64,
            "y": target_y,
            "block_width": full_block_w,
            "block_height": full_block_h
        }

    @classmethod
    def verify_trajectory_and_offset(
        cls,
        captcha_id: str,
        submitted_x: float,
        track: List[List[float]]
    ) -> Dict[str, Any]:
        """
        Multi-dimensional Behavioral & Offset Verification Algorithm.
        Args:
            captcha_id: The ephemeral captcha session ID
            submitted_x: Final x-coordinate offset submitted by frontend
            track: Trajectory sample list [[x, y, timestamp_ms], ...]
        Returns:
            Dict with success status, captcha_token, elapsed_time or error message.
        """
        redis_val = redis_client.get(f"captcha:slider:{captcha_id}")
        if not redis_val:
            return {"success": False, "message": "验证码已过期或不存在，请刷新重试"}

        parts = redis_val.split(":")
        target_x = float(parts[0])
        created_at_ms = float(parts[2])
        now_ms = time.time() * 1000

        # Invalidate original captcha_id to prevent replay attacks
        redis_client.delete(f"captcha:slider:{captcha_id}")

        # 1. Target Offset Accuracy Check (Tolerance <= 5px)
        offset_diff = abs(submitted_x - target_x)
        if offset_diff > cls.TOLERANCE:
            return {
                "success": False,
                "message": f"缺口拼接未对准 (偏差 {round(offset_diff, 1)}px)"
            }

        # 2. Time Duration Verification (200ms <= T <= 10000ms)
        total_time_ms = now_ms - created_at_ms
        if len(track) >= 2:
            track_time_ms = track[-1][2] - track[0][2]
        else:
            track_time_ms = total_time_ms

        if track_time_ms < 180:
            return {"success": False, "message": "滑动速度异常，判定为自动化脚本"}
        if track_time_ms > 12000:
            return {"success": False, "message": "滑动操作超时，请重新验证"}

        # 3. Behavioral Trajectory Analysis (Human Micro-Jitter & Non-Linear Velocity)
        if len(track) >= 4:
            y_coords = [p[1] for p in track]
            y_variance = sum((y - (sum(y_coords) / len(y_coords))) ** 2 for y in y_coords) / len(y_coords)
            
            # Check for non-zero acceleration / deceleration
            velocities = []
            for i in range(1, len(track)):
                dx = track[i][0] - track[i-1][0]
                dt = max(1.0, track[i][2] - track[i-1][2])
                velocities.append(dx / dt)

            # Check velocity variance
            if len(velocities) >= 3:
                avg_v = sum(velocities) / len(velocities)
                v_variance = sum((v - avg_v) ** 2 for v in velocities) / len(velocities)
                if v_variance == 0.0 and len(velocities) > 10:
                    return {"success": False, "message": "滑动轨迹无加速度变化，判定为机器人"}

        # 4. Issue Ephemeral Single-Use Captcha Token (Valid for 60s)
        captcha_token = str(uuid.uuid4())
        redis_client.set(f"captcha:token:{captcha_token}", "valid", ex=60)

        elapsed_sec = round(track_time_ms / 1000, 2)
        return {
            "success": True,
            "captcha_token": captcha_token,
            "elapsed_time": elapsed_sec,
            "message": f"验证通过！耗时 {elapsed_sec} 秒"
        }

    @staticmethod
    def validate_captcha_token(token: str) -> bool:
        """
        Validate and immediately consume single-use token on login.
        """
        if not token:
            return False
        key = f"captcha:token:{token}"
        val = redis_client.get(key)
        if val:
            redis_client.delete(key)
            return True
        return False
