"""Render the exact 120 frame loop from loop.blend to preview.mp4 (5.000 s at 24 fps).
Run: blender -b loop.blend --python-exit-code 1 -P render_preview.py -- <out_file>
"""
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.resolution_percentage = 100
sc.render.image_settings.media_type = 'VIDEO'
sc.render.image_settings.file_format = 'FFMPEG'
sc.render.ffmpeg.format = 'MPEG4'
sc.render.ffmpeg.codec = 'H264'
sc.render.ffmpeg.constant_rate_factor = 'HIGH'
sc.render.ffmpeg.ffmpeg_preset = 'GOOD'
sc.render.ffmpeg.gopsize = 24
sc.render.ffmpeg.audio_codec = 'NONE'
sc.render.filepath = out
bpy.ops.render.render(animation=True)
print("RESULT rendered", sc.frame_start, sc.frame_end)
